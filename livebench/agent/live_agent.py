"""
Main agent class for task completion with decision-making framework
"""

import os
import json
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path

from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openai import ChatOpenAI
from agent.economic_tracker import track_response_tokens
from dotenv import load_dotenv

# Import framework components
import sys
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from agent.economic_tracker import EconomicTracker
from agent.message_formatter import format_tool_result_message, format_result_for_logging
from work.task_manager import TaskManager
from work.evaluator import WorkEvaluator
from prompts.live_agent_prompt import (
    get_live_agent_system_prompt,
    get_work_task_prompt,
    format_cost_update,
    STOP_SIGNAL
)
from livebench.utils.logger import LiveBenchLogger, set_global_logger

# Load environment variables
load_dotenv()


class LiveAgent:
    """
    LiveAgent - AI agent for economic survival simulation

    Core functionality:
    1. Economic tracking (balance, token costs, income)
    2. Daily decision-making (work vs learn)
    3. Work task execution
    4. Learning and knowledge accumulation
    5. Survival management
    """

    def __init__(
        self,
        signature: str,
        basemodel: str,
        initial_balance: float = 1000.0,
        input_token_price: float = 0.01,
        output_token_price: float = 0.03,
        max_work_payment: float = 50.0,
        mcp_config: Optional[Dict[str, Dict[str, Any]]] = None,
        data_path: Optional[str] = None,
        max_steps: int = 20,
        max_retries: int = 5,
        base_delay: float = 1.0,
        api_timeout: float = 120.0,
        openai_base_url: Optional[str] = None,
        # New task source parameters
        task_source_type: str = "parquet",
        task_source_path: Optional[str] = None,
        inline_tasks: Optional[List[Dict]] = None,
        # New filtering and assignment parameters
        agent_filters: Optional[Dict[str, List[str]]] = None,
        agent_assignment: Optional[Dict[str, Any]] = None,
        # Task value pricing
        task_values_path: Optional[str] = None,
        # Evaluation parameters
        use_llm_evaluation: bool = True,
        meta_prompts_dir: str = "./eval/meta_prompts",
        # Tasks per day parameter
        tasks_per_day: int = 1,
        # Multimodal support parameter
        supports_multimodal: bool = True,
        # Skill module (optional): when True, append skill tools and skill section to prompt
        skill_enabled: bool = False,
        # When True (default), merge global built-in skills with agent store; when False, only agent store
        skill_use_builtin: bool = True,
        # Force daily activity ("work" or "learn"). When set to "work", learn tool is disabled.
        force_activity: Optional[str] = None,
    ):
        """
        Initialize LiveAgent

        Args:
            signature: Agent signature/name
            basemodel: Base model name
            initial_balance: Starting balance in dollars
            input_token_price: Price per 1K input tokens
            output_token_price: Price per 1K output tokens
            max_work_payment: Maximum payment for work tasks (used as default if no task values)
            mcp_config: MCP tool configuration
            data_path: Path to store agent data
            max_steps: Maximum reasoning steps per session
            max_retries: Maximum retry attempts for API calls (default: 5)
            base_delay: Base delay in seconds for exponential backoff retries (default: 1.0)
            api_timeout: Timeout in seconds for each API call (default: 120.0)
            openai_base_url: OpenAI API base URL
            task_source_type: Type of task source ("parquet", "jsonl", or "inline")
            task_source_path: Path to task source file
            inline_tasks: List of inline tasks
            agent_filters: Filter criteria for task selection
            agent_assignment: Explicit task assignment configuration
            task_values_path: Path to task_values.jsonl with calculated task prices
            use_llm_evaluation: Whether to use LLM-based evaluation
            meta_prompts_dir: Path to evaluation meta-prompts directory
            tasks_per_day: Number of tasks agent can work on per day
            supports_multimodal: Whether the model supports multimodal (image) inputs
            skill_enabled: Whether to load skill tools and inject skill section into prompt
            skill_use_builtin: When True, load both global and agent skills; when False, only agent skills
        """
        self.signature = signature
        self.skill_enabled = skill_enabled
        self.skill_use_builtin = skill_use_builtin
        self.basemodel = basemodel
        self.max_steps = max_steps
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.api_timeout = api_timeout
        self.tasks_per_day = tasks_per_day
        self.supports_multimodal = supports_multimodal
        self.force_activity = (force_activity or "").strip().lower() or None

        # Set data path
        self.data_path = data_path or f"./livebench/data/agent_data/{signature}"
        
        # Initialize logger
        self.logger = LiveBenchLogger(signature=signature, data_path=self.data_path)
        set_global_logger(self.logger)

        # Set OpenAI configuration
        self.openai_base_url = openai_base_url or os.getenv("OPENAI_API_BASE")
        self.is_openrouter = (self.openai_base_url or "") == "https://openrouter.ai/api/v1"

        # Initialize components
        self.economic_tracker = EconomicTracker(
            signature=signature,
            initial_balance=initial_balance,
            input_token_price=input_token_price,
            output_token_price=output_token_price,
            data_path=os.path.join(self.data_path, "economic")
        )

        # Initialize TaskManager with new parameters
        self.task_manager = TaskManager(
            task_source_type=task_source_type,
            task_source_path=task_source_path,
            inline_tasks=inline_tasks,
            task_data_path=self.data_path,
            agent_filters=agent_filters,
            agent_assignment=agent_assignment,
            task_values_path=task_values_path,
            default_max_payment=max_work_payment
        )

        self.evaluator = WorkEvaluator(
            max_payment=max_work_payment,
            data_path=self.data_path,
            use_llm_evaluation=use_llm_evaluation,
            meta_prompts_dir=meta_prompts_dir
        )

        # Set MCP configuration
        self.mcp_config = mcp_config or self._get_default_mcp_config()

        # MCP and AI components
        self.client: Optional[MultiServerMCPClient] = None
        self.tools: Optional[List] = None
        self.model: Optional[ChatOpenAI] = None
        self.agent: Optional[Any] = None

        # Daily state
        self.current_date: Optional[str] = None
        self.current_task: Optional[Dict] = None
        self.daily_activity: Optional[str] = None  # "work" or "learn"
        self.daily_work_income: float = 0.0
        self.daily_trading_profit: float = 0.0

        # Per-session result tracking (reset each run_daily_session call)
        self.last_evaluation_score: float = 0.0
        self.last_work_submitted: bool = False
        self._logged_response_metadata: bool = False  # print full metadata once per agent lifetime
        # Attempt counter used by exhaust mode (set before calling run_daily_session)
        self.current_attempt: int = 1

    def _get_default_mcp_config(self) -> Dict[str, Dict[str, Any]]:
        """Get default MCP configuration - Work and Learn only"""
        config = {
            "livebench": {
                "transport": "streamable_http",
                "url": f"http://localhost:{os.getenv('LIVEBENCH_HTTP_PORT', '8010')}/mcp",
            }
        }
        # Trading functionality disabled - focusing on work and learn capabilities only
        return config

    async def initialize(self) -> None:
        """Initialize agent components"""
        print(f"🚀 Initializing LiveAgent: {self.signature}")

        # Initialize economic tracker
        self.economic_tracker.initialize()

        # Load tasks
        self.task_manager.load_tasks()

        # Get tools directly (no MCP)
        from livebench.tools.direct_tools import get_all_tools, set_global_state as set_tool_state

        allow_learn = not (self.force_activity == "work")
        allow_decide_activity = self.force_activity is None
        self.tools = get_all_tools(
            skill_enabled=self.skill_enabled,
            allow_decide_activity=allow_decide_activity,
            allow_learn=allow_learn,
        )
        print(f"✅ Loaded {len(self.tools)} tools")
        if self.skill_enabled:
            print("   📚 Skills module enabled (get_skills, search_skills, get_skill_content)")

        # Set tool state
        set_tool_state(
            signature=self.signature,
            economic_tracker=self.economic_tracker,
            task_manager=self.task_manager,
            evaluator=self.evaluator,
            current_date=self.current_date,
            current_task=self.current_task,
            data_path=self.data_path,
            supports_multimodal=self.supports_multimodal,
            use_builtin_skills=getattr(self, "skill_use_builtin", True),
        )

        # Create AI model with custom httpx clients (bypass proxy)
        import httpx
        http_client_sync = httpx.Client(
            timeout=self.api_timeout,
            trust_env=False  # Don't use environment proxy settings
        )
        http_client_async = httpx.AsyncClient(
            timeout=self.api_timeout,
            trust_env=False
        )

        self.model = ChatOpenAI(
            model=self.basemodel,
            base_url=self.openai_base_url,
            max_retries=3,
            timeout=self.api_timeout,
            http_client=http_client_sync,
            http_async_client=http_client_async
        )

        print(f"✅ LiveAgent {self.signature} initialization completed")

    def _prepare_reference_files(self, date: str, task: Dict) -> List[str]:
        """
        Copy task reference files to agent's sandbox AND upload to E2B sandbox for code execution.
        
        Args:
            date: Current date
            task: Task dictionary with reference_files list (can be list or numpy array)
            
        Returns:
            List of remote paths in E2B sandbox (e.g., ["/home/user/reference_files/file.pdf"])
        """
        import shutil
        
        reference_files = task.get('reference_files', [])
        
        # Handle both list and numpy array (from pandas DataFrame)
        if reference_files is None:
            return []
        try:
            if len(reference_files) == 0:
                return []
        except (TypeError, AttributeError):
            # If len() fails, it's not a sequence
            return []
        
        # Get absolute paths to reference files (used by inline task / skill self-evolution experiment)
        ref_file_paths = self.task_manager.get_task_reference_files(task)
        base_path = getattr(self.task_manager, "reference_files_base_path", None)
        _msg = f"   [ref-file] Preparing {len(ref_file_paths)} reference file(s), base={base_path}"
        print(_msg)
        sys.stdout.flush()

        # File-based debug log when REF_FILES_DEBUG=1 (survives subprocess stdout)
        _ref_debug = os.environ.get("REF_FILES_DEBUG", "").strip() in ("1", "true", "yes")
        _debug_lines = []
        if _ref_debug:
            _debug_lines.append(f"cwd={os.getcwd()!r}")
            _debug_lines.append(f"base_path={base_path!r}")
            _debug_lines.append(f"base_exists={os.path.exists(base_path) if base_path else 'N/A'}")
            _debug_lines.append(f"ref_file_paths_count={len(ref_file_paths)}")
        
        # Create sandbox directory for reference files (host filesystem)
        sandbox_dir = os.path.join(self.data_path, "sandbox", date, "reference_files")
        os.makedirs(sandbox_dir, exist_ok=True)
        
        copied_files = []
        missing_files = []
        e2b_remote_paths = []
        
        def _resolve_ref_path(candidate: str) -> str:
            """Return a path that exists. If candidate does not exist, try same dir by basename match or single-file fallback (handles encoding/parquet mismatch)."""
            from pathlib import Path
            candidate = os.path.normpath(candidate)
            if os.path.exists(candidate):
                return candidate
            parent = os.path.normpath(os.path.dirname(candidate))
            base = os.path.basename(candidate)
            entries = []
            parent_resolved = None
            try:
                # Use pathlib resolve so we get a real filesystem path (helps on Windows with encoding)
                parent_p = Path(parent)
                if not parent_p.exists():
                    print(f"   [ref-file] parent does not exist: {parent!r}")
                    sys.stdout.flush()
                    return candidate
                parent_resolved = parent_p.resolve()
                entries = [f.name for f in parent_resolved.iterdir() if f.is_file()]
            except OSError as e:
                print(f"   [ref-file] listdir failed for parent={parent!r}: {e}")
                sys.stdout.flush()
                self.logger.terminal_print(f"   [ref-file] listdir failed for parent={parent!r}: {e}")
                return candidate
            except Exception as e:
                print(f"   [ref-file] resolve failed for parent={parent!r}: {e}")
                sys.stdout.flush()
                return candidate
            # Use pathlib for return path so it matches what the filesystem sees (critical on Windows)
            def _ret(pth):
                s = os.path.normpath(str(pth))
                return s if os.path.exists(s) else None

            for name in entries:
                if name == base:
                    r = _ret(parent_resolved / name)
                    if r:
                        return r
                elif os.path.normcase(name) == os.path.normcase(base):
                    r = _ret(parent_resolved / name)
                    if r:
                        return r
            if len(entries) == 1:
                r = _ret(parent_resolved / entries[0])
                if r:
                    return r
                print(f"   [ref-file] single file path not found: {parent_resolved / entries[0]!s}")
                sys.stdout.flush()
            else:
                base_stem, base_ext = os.path.splitext(base)
                for name in entries:
                    stem, ext = os.path.splitext(name)
                    if ext == base_ext and (stem in base_stem or base_stem in stem or os.path.normcase(stem) == os.path.normcase(base_stem)):
                        r = _ret(parent_resolved / name)
                        if r:
                            return r
                print(f"   [ref-file] no match: basename={base!r}, parent_entries={len(entries)}")
                sys.stdout.flush()
            return candidate
        

        for idx, candidate_path in enumerate(ref_file_paths):
            src_path = _resolve_ref_path(candidate_path)
            exists_after = os.path.exists(src_path)
            if _ref_debug:
                parent = os.path.dirname(candidate_path)
                try:
                    from pathlib import Path as _Path
                    parent_exists = _Path(parent).exists()
                except Exception:
                    parent_exists = "?"
                _debug_lines.append(f"[{idx+1}] candidate={candidate_path!r}")
                _debug_lines.append(f"    candidate_exists={os.path.exists(candidate_path)} parent_exists={parent_exists}")
                _debug_lines.append(f"    resolved={src_path!r} resolved_exists={exists_after}")
            if exists_after:
                # Copy file to sandbox, preserving filename
                filename = os.path.basename(src_path)
                dest_path = os.path.join(sandbox_dir, filename)
                from livebench.utils.path_io import path_for_io
                dest_for_io = path_for_io(dest_path) or dest_path
                try:
                    shutil.copy2(src_path, dest_for_io)
                    copied_files.append(filename)
                    if _ref_debug:
                        _debug_lines.append(f"    -> COPIED {filename}")
                    self.logger.debug(
                        f"Copied reference file: {filename}",
                        context={"src": src_path, "dest": dest_path},
                        print_console=False
                    )
                    
                    # Upload to E2B sandbox for execute_code access
                    try:
                        from livebench.tools.productivity.code_execution_sandbox import upload_task_reference_files
                        remote_paths = upload_task_reference_files([dest_for_io])
                        if remote_paths:
                            e2b_remote_paths.extend(remote_paths)
                    except Exception as e:
                        self.logger.warning(
                            f"Failed to upload {filename} to E2B sandbox: {str(e)}",
                            context={"file": filename},
                            print_console=False
                        )
                    
                except Exception as e:
                    if _ref_debug:
                        _debug_lines.append(f"    -> COPY FAILED: {type(e).__name__}: {e}")
                    self.logger.warning(
                        f"Failed to copy reference file: {filename}",
                        context={"src": src_path, "error": str(e)},
                        print_console=False
                    )
                    print(f"   [ref-file] Copy failed: {filename} -> {e}")
                    sys.stdout.flush()
            else:
                missing_files.append(src_path)
                if _ref_debug:
                    _debug_lines.append(f"    -> MISSING")
                print(f"   [ref-file] MISSING (not found after resolve): {os.path.basename(src_path)}")
                sys.stdout.flush()
                self.logger.warning(
                    f"Reference file not found: {src_path}",
                    context={"task_id": task.get('task_id')},
                    print_console=False
                )

        if _ref_debug and _debug_lines:
            try:
                # Use normpath so the path is consistent (no mixed slashes when data_path came from Path.as_posix())
                _log_path = os.path.normpath(os.path.join(self.data_path, "ref_files_debug.log"))
                with open(_log_path, "w", encoding="utf-8") as _f:
                    _f.write("\n".join(_debug_lines))
                print(f"   [ref-file] Debug log written: {_log_path}")
                sys.stdout.flush()
            except Exception as _e:
                print(f"   [ref-file] Failed to write debug log: {_e}")
                sys.stdout.flush()
        
        if copied_files:
            self.logger.terminal_print(f"📎 Copied {len(copied_files)} reference file(s) to sandbox")
            if e2b_remote_paths:
                self.logger.terminal_print(f"   📤 Uploaded {len(e2b_remote_paths)} file(s) to E2B sandbox")
            self.logger.info(
                "Reference files prepared",
                context={
                    "date": date,
                    "task_id": task.get('task_id'),
                    "copied": copied_files,
                    "missing": missing_files,
                    "e2b_paths": e2b_remote_paths
                },
                print_console=False
            )
        
        if missing_files:
            self.logger.terminal_print(f"⚠️ Warning: {len(missing_files)} reference file(s) not found")
            for m in missing_files:
                parent_dir = os.path.dirname(m)
                self.logger.terminal_print(f"   Missing: {os.path.basename(m)}")
                self.logger.terminal_print(f"   Tried parent: {parent_dir}")
                self.logger.terminal_print(f"   (Check: dir \"{parent_dir}\" )")
        
        # Store E2B paths in task for prompt generation
        task['e2b_reference_paths'] = e2b_remote_paths
        return e2b_remote_paths

    def _setup_logging(self, date: str) -> str:
        """Set up log file path for activity messages"""
        log_path = os.path.join(self.data_path, 'activity_logs', date)
        os.makedirs(log_path, exist_ok=True)
        return os.path.join(log_path, "log.jsonl")

    def _log_message(self, log_file: str, messages: List[Dict[str, str]]) -> None:
        """Log messages to log file"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "signature": self.signature,
            "messages": messages
        }
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

    async def _ainvoke_with_retry(self, messages: List[Dict[str, str]], timeout: float = 120.0) -> Any:
        """
        Agent invocation with retry, timeout, and token tracking
        
        Args:
            messages: List of messages to send to the agent
            timeout: Maximum time in seconds to wait for API response (default: 120s)
            
        Returns:
            Agent response
            
        Raises:
            Exception: If all retry attempts fail
        """
        for attempt in range(1, self.max_retries + 1):
            try:
                # Convert messages to LangChain format
                from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

                lc_messages = []
                for msg in messages:
                    role = msg.get("role", "user")
                    content = msg.get("content", "")
                    
                    # Handle multimodal content (list of content items) vs string content
                    # Multimodal messages have content as a list of dicts with type/text/image_url
                    # String messages have content as a simple string

                    if role == "system":
                        lc_messages.append(SystemMessage(content=content))
                    elif role == "assistant" or role == "ai":
                        lc_messages.append(AIMessage(content=content))
                    else:  # user or human
                        # LangChain HumanMessage can accept both string and list[dict] content
                        lc_messages.append(HumanMessage(content=content))

                # Invoke the model with explicit timeout
                try:
                    response = await asyncio.wait_for(
                        self.agent.ainvoke(lc_messages),
                        timeout=timeout
                    )
                except asyncio.TimeoutError:
                    raise TimeoutError(f"API call timed out after {timeout} seconds")

                # Track token usage from API response
                self._track_tokens_from_response(response)

                return response

            except Exception as e:
                error_type = type(e).__name__
                is_timeout = isinstance(e, (asyncio.TimeoutError, TimeoutError))
                
                self.logger.warning(
                    f"Agent invocation attempt {attempt}/{self.max_retries} failed",
                    context={
                        "attempt": attempt,
                        "max_retries": self.max_retries,
                        "error_type": error_type,
                        "is_timeout": is_timeout,
                        "message_count": len(messages)
                    },
                    print_console=True
                )
                
                if attempt == self.max_retries:
                    self.logger.error(
                        f"Agent invocation failed after {self.max_retries} attempts",
                        exception=e,
                        print_console=True
                    )
                    raise e
                    
                retry_delay = self.base_delay * attempt
                self.logger.terminal_print(f"⚠️ Attempt {attempt} failed ({error_type}), retrying in {retry_delay}s...")
                self.logger.terminal_print(f"   Error: {str(e)[:200]}")
                await asyncio.sleep(retry_delay)

    def _track_tokens_from_response(self, response: Any) -> None:
        """Track token usage from the API response.

        Delegates to the shared track_response_tokens() function.
        Prints the full response_metadata once per agent lifetime for inspection.
        """
        if not self._logged_response_metadata:
            self.logger.terminal_print(
                f"   📋 response_metadata (first call): {response.response_metadata}"
            )
            self._logged_response_metadata = True

        track_response_tokens(response, self.economic_tracker, self.logger, self.is_openrouter)

    async def _execute_tool(self, tool_name: str, tool_args: Dict[str, Any]) -> Any:
        """Execute a tool by name with given arguments"""
        # Find the tool
        for tool in self.tools:
            if hasattr(tool, 'name') and tool.name == tool_name:
                try:
                    # LangChain tools can be invoked directly
                    result = tool.invoke(tool_args)

                    # Print result to console and terminal log (format for logging to avoid binary data)
                    formatted_result = format_result_for_logging(result)
                    self.logger.terminal_print(f"   ✅ Result: {formatted_result}")
                    
                    # Log successful tool execution
                    self.logger.debug(
                        f"Tool executed successfully: {tool_name}",
                        context={"tool": tool_name, "args": str(tool_args)[:200]},
                        print_console=False
                    )

                    return result
                except Exception as e:
                    error_msg = f"Error: {str(e)}"
                    self.logger.terminal_print(f"   ❌ {error_msg}")
                    
                    # Log tool execution error
                    self.logger.error(
                        f"Tool execution failed: {tool_name}",
                        context={"tool": tool_name, "args": tool_args},
                        exception=e,
                        print_console=False
                    )
                    
                    import traceback
                    traceback.print_exc()
                    return error_msg

        error = f"Tool {tool_name} not found"
        self.logger.terminal_print(f"   ❌ {error}")
        
        # Log tool not found error
        self.logger.error(
            f"Tool not found: {tool_name}",
            context={
                "tool": tool_name,
                "available_tools": [t.name for t in self.tools if hasattr(t, 'name')]
            },
            print_console=False
        )
        
        return error

    async def run_daily_session(self, date: str) -> Optional[str]:
        """
        Run daily session: decision-making and activity execution

        Args:
            date: Date string (YYYY-MM-DD)

        Returns:
            "NO_TASKS_AVAILABLE" if no tasks left, "ERROR" on error, None on success
        """
        # Set up logging (both conversation and terminal logs)
        log_file = self._setup_logging(date)
        self.logger.setup_terminal_log(date)
        
        self.logger.terminal_print(f"\n{'='*60}")
        self.logger.terminal_print(f"📅 Daily Session: {date}")
        self.logger.terminal_print(f"   Agent: {self.signature}")
        self.logger.terminal_print(f"{'='*60}\n")

        self.current_date = date
        self.daily_work_income = 0.0
        self.daily_trading_profit = 0.0
        self.last_evaluation_score = 0.0
        self.last_work_submitted = False
        session_api_error = False

        # Check if bankrupt
        if self.economic_tracker.is_bankrupt():
            self.logger.terminal_print("💀 Agent is BANKRUPT! Cannot continue.")
            self.logger.error(
                "Agent is bankrupt and cannot continue",
                context={"date": date, "balance": self.economic_tracker.get_balance()},
                print_console=False
            )
            return

        # Select daily work task
        try:
            self.current_task = self.task_manager.select_daily_task(date, self.signature)
            if not self.current_task:
                self.logger.terminal_print("🛑 No tasks available - stopping agent")
                self.logger.info(
                    "Agent stopped: No more tasks available",
                    context={"date": date},
                    print_console=False
                )
                # Return special marker to indicate no tasks available
                return "NO_TASKS_AVAILABLE"
            else:
                # Start tracking costs for this task with the task's date
                self.economic_tracker.start_task(self.current_task['task_id'], date=date)
                # Capture start time for wall-clock tracking
                task_start_dt = datetime.now()
        except Exception as e:
            self.logger.error(
                f"Error selecting daily task for {date}",
                context={"date": date},
                exception=e,
                print_console=True
            )
            self.current_task = None
            return "ERROR"

        # Copy reference files to sandbox for agent access (skill self-evolution / inline task with reference_files)
        if self.current_task:
            ref_files = self.current_task.get('reference_files')
            # Handle both list and numpy array (from pandas)
            has_ref_files = False
            if ref_files is not None:
                try:
                    # Check if it has any elements (works for list, numpy array, etc.)
                    has_ref_files = len(ref_files) > 0
                except (TypeError, AttributeError):
                    # If len() fails, try truthiness (for non-sequence types)
                    has_ref_files = bool(ref_files)
            
            if has_ref_files:
                try:
                    self._prepare_reference_files(date, self.current_task)
                except Exception as e:
                    self.logger.error(
                        "Failed to prepare reference files",
                        context={"date": date, "task_id": self.current_task.get('task_id')},
                        exception=e,
                        print_console=True
                    )
                    # Don't fail the session, but agent won't have reference files

        # Update tool state with current date and task
        try:
            from livebench.tools.direct_tools import set_global_state as set_tool_state
            set_tool_state(
                signature=self.signature,
                economic_tracker=self.economic_tracker,
                task_manager=self.task_manager,
                evaluator=self.evaluator,
                current_date=date,
                current_task=self.current_task,
                data_path=self.data_path,
                supports_multimodal=self.supports_multimodal,
                use_builtin_skills=getattr(self, "skill_use_builtin", True),
            )
            
            # Log task assignment for debugging
            if self.current_task:
                self.logger.terminal_print(f"✅ Task state updated: {self.current_task.get('task_id', 'unknown')}")
                self.logger.info(
                    f"Task state set successfully",
                    context={
                        "date": date,
                        "task_id": self.current_task.get('task_id', 'unknown'),
                        "sector": self.current_task.get('sector', 'unknown')
                    },
                    print_console=False
                )
            else:
                self.logger.terminal_print(f"⚠️ WARNING: No task was selected for {date}")
                self.logger.warning(
                    f"Task state set with no task",
                    context={"date": date},
                    print_console=False
                )
        except Exception as e:
            self.logger.error(
                "Failed to set global tool state",
                context={"date": date},
                exception=e,
                print_console=True
            )
            raise

        # Create agent with today's system prompt
        economic_state = self.economic_tracker.get_summary()
        skill_section = None
        if self.skill_enabled:
            try:
                from livebench.skill import get_skill_prompt_section
                skill_section = get_skill_prompt_section(
                    self.signature,
                    self.data_path,
                    use_builtin=getattr(self, "skill_use_builtin", True),
                )
            except ImportError:
                pass
        # Actual host path for reference files (so read_file gets correct path in single_task_debug etc.)
        host_reference_dir = os.path.join(self.data_path, "sandbox", date, "reference_files")
        if not os.path.isabs(host_reference_dir):
            host_reference_dir = os.path.abspath(host_reference_dir)
        system_prompt = get_live_agent_system_prompt(
            date=date,
            signature=self.signature,
            economic_state=economic_state,
            work_task=self.current_task,
            max_steps=self.max_steps,
            skill_section=skill_section or None,
            host_reference_dir=host_reference_dir,
            force_activity=getattr(self, "force_activity", None),
        )

        # Bind tools to the model
        self.agent = self.model.bind_tools(self.tools)

        # Initial messages
        if self.force_activity == "work":
            first_user_msg = (
                f"Today is {date}. Your activity is forced: WORK. "
                f"Start working on today's task immediately. Do not choose LEARN."
            )
        elif self.force_activity == "learn":
            first_user_msg = (
                f"Today is {date}. Your activity is forced: LEARN. "
                f"Start learning immediately. Do not attempt the work task."
            )
        else:
            first_user_msg = f"Today is {date}. Analyze your situation and decide your activity."

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": first_user_msg},
        ]

        self._log_message(log_file, messages)

        # Agent reasoning loop with tool calling (use config max_steps, not hardcoded limit)
        max_iterations = self.max_steps
        activity_completed = False
        # Consecutive turns with no tool_calls while work not submitted: nudge at most this many times, then exit to wrap-up
        consecutive_no_tool_calls = 0
        max_nudge_no_tool_calls = 2

        for iteration in range(max_iterations):
            self.logger.terminal_print(f"\n🔄 Iteration {iteration + 1}/{max_iterations}")

            try:
                # Call agent with timeout and retry
                try:
                    response = await self._ainvoke_with_retry(messages, timeout=self.api_timeout)
                except Exception as api_error:
                    # API call failed after all retries - skip this task and continue
                    self.logger.terminal_print(f"\n❌ API call failed after {self.max_retries} retries")
                    self.logger.terminal_print(f"   Error: {str(api_error)[:200]}")
                    self.logger.terminal_print(f"   ⏭️ Skipping current task and continuing...")
                    self.logger.error(
                        f"API call failed, skipping task",
                        context={
                            "date": date,
                            "task_id": self.current_task.get('task_id') if self.current_task else None,
                            "iteration": iteration + 1,
                            "max_retries": self.max_retries
                        },
                        exception=api_error,
                        print_console=False
                    )
                    # End task tracking before breaking
                    try:
                        self.economic_tracker.end_task()
                    except Exception:
                        pass
                    # Mark as API error for exhaust mode tracking
                    session_api_error = True
                    # Break out of iteration loop to skip this task
                    break

                # Extract response content
                if hasattr(response, 'content'):
                    agent_response = response.content
                else:
                    agent_response = str(response)

                # Show agent thinking (truncated)
                if len(agent_response) > 200:
                    self.logger.terminal_print(f"💭 Agent: {agent_response[:200]}...")
                else:
                    self.logger.terminal_print(f"💭 Agent: {agent_response}")

                # Check for tool calls
                if hasattr(response, 'tool_calls') and response.tool_calls:
                    consecutive_no_tool_calls = 0  # Reset when model uses tools
                    self.logger.terminal_print(f"🔧 Tool calls: {len(response.tool_calls)}")

                    # Add AI message
                    messages.append({"role": "assistant", "content": agent_response})

                    # Execute each tool call
                    for tool_call in response.tool_calls:
                        tool_name = tool_call.get('name', 'unknown')
                        tool_args = tool_call.get('args', {})

                        self.logger.terminal_print(f"\n   📞 Calling: {tool_name}")
                        self.logger.terminal_print(f"   📥 Args: {str(tool_args)[:100]}...")

                        # Find and execute the tool
                        tool_result = await self._execute_tool(tool_name, tool_args)

                        # Check if activity was completed
                        if tool_name == 'submit_work':
                            # End task tracking
                            self.economic_tracker.end_task()
                            self.last_work_submitted = True

                            # Check if work was successful and extract payment
                            result_dict = tool_result if isinstance(tool_result, dict) else {}
                            if 'actual_payment' in result_dict or 'payment' in result_dict:
                                try:
                                    if not isinstance(result_dict, dict):
                                        result_dict = eval(str(tool_result))
                                    # Use actual_payment which respects evaluation threshold
                                    actual_payment = result_dict.get('actual_payment', result_dict.get('payment', 0))
                                    evaluation_score = result_dict.get('evaluation_score', 0.0)
                                    self.last_evaluation_score = evaluation_score
                                    # Detect learn-only evolution tasks: no payment / income logs.
                                    task_id = ""
                                    is_learn_only = False
                                    if self.current_task:
                                        task_id = str(self.current_task.get("task_id") or "")
                                        is_learn_only = bool(self.current_task.get("learn_only")) or task_id.startswith("learn-")

                                    if is_learn_only:
                                        # For learn-only sessions, treat successful evaluation as completion,
                                        # but do not log earnings or quality/threshold messages.
                                        activity_completed = True
                                    else:
                                        if actual_payment > 0:
                                            self.daily_work_income += actual_payment
                                            self.logger.terminal_print(f"\n   💰 Earned: ${actual_payment:.2f} (Score: {evaluation_score:.2f})")
                                            activity_completed = True
                                        elif evaluation_score > 0:
                                            # Work was submitted but didn't meet quality threshold
                                            self.logger.terminal_print(f"\n   ⚠️  Quality score {evaluation_score:.2f} below threshold - no payment")
                                            activity_completed = True
                                except:
                                    pass
                            if 'success' in str(tool_result).lower():
                                activity_completed = True
                        elif tool_name == 'learn' and 'success' in str(tool_result).lower():
                            activity_completed = True

                        # Add tool result to messages (handle multimodal content)
                        tool_message = format_tool_result_message(
                            tool_name, tool_result, tool_args, activity_completed
                        )
                        messages.append(tool_message)
                    # If activity is completed, stop the loop
                    if activity_completed:
                        self.logger.terminal_print(f"\n✅ Activity completed successfully!")
                        break

                    # Continue loop to get next response
                    continue

                # No tool calls this turn: decide whether "done" or "nudge and continue"
                self._log_message(log_file, [{"role": "assistant", "content": agent_response}])
                if activity_completed or not self.current_task:
                    self.logger.terminal_print(f"\n✅ Agent completed daily session")
                    break
                # Work task active but not submitted: avoid both (1) treating as done and (2) nudging forever
                consecutive_no_tool_calls += 1
                if consecutive_no_tool_calls > max_nudge_no_tool_calls:
                    self.logger.terminal_print(
                        f"\n⚠️ No tool calls for {consecutive_no_tool_calls} turn(s); work not submitted—exiting to wrap-up."
                    )
                    break
                self.logger.terminal_print(
                    f"\n⚠️ No tool calls this turn (work not submitted yet); prompting to continue ({consecutive_no_tool_calls}/{max_nudge_no_tool_calls})."
                )
                messages.append({"role": "assistant", "content": agent_response})
                messages.append({
                    "role": "user",
                    "content": "Continue. You have not submitted work yet; use a tool call to proceed (e.g. read_file, execute_code) or submit_work when ready. Do not reply with only text—call at least one tool."
                })
                continue

            except Exception as e:
                # Unexpected error (not from API call) - log and re-raise
                self.logger.terminal_print(f"\n❌ Unexpected error in daily session: {str(e)}")
                self.logger.error(
                    f"Unexpected error in daily session iteration {iteration + 1}",
                    context={
                        "date": date,
                        "iteration": iteration + 1,
                        "max_iterations": max_iterations,
                        "activity_completed": activity_completed
                    },
                    exception=e,
                    print_console=False
                )
                import traceback
                traceback.print_exc()
                raise

        # WRAP-UP WORKFLOW: If activity not completed, try to collect and submit artifacts
        if not activity_completed and self.current_task:
            self.logger.terminal_print("\n⚠️ Iteration limit reached without task completion")
            self.logger.terminal_print("🔄 Initiating wrap-up workflow to collect artifacts...")
            
            try:
                from livebench.agent.wrapup_workflow import create_wrapup_workflow
                
                # Create sandbox directory path for this date
                sandbox_dir = os.path.join(
                    self.data_path,
                    "sandbox",
                    date
                )
                
                # Create and run wrap-up workflow with conversation context
                wrapup = create_wrapup_workflow(llm=self.model, logger=self.logger, economic_tracker=self.economic_tracker, is_openrouter=self.is_openrouter)
                wrapup_result = await wrapup.run(
                    date=date,
                    task=self.current_task,
                    sandbox_dir=sandbox_dir,
                    conversation_history=messages  # Pass conversation for context
                )
                
                # Process results
                submission = wrapup_result.get("submission_result")
                if submission and isinstance(submission, dict):
                    if submission.get("success"):
                        payment = submission.get("payment", 0)
                        if payment > 0:
                            self.daily_work_income += payment
                            activity_completed = True
                            self.logger.terminal_print(f"\n✅ Wrap-up workflow succeeded! Earned: ${payment:.2f}")
                    else:
                        self.logger.terminal_print(f"\n⚠️ Wrap-up workflow completed but submission failed")
                else:
                    self.logger.terminal_print(f"\n⚠️ Wrap-up workflow did not submit any work")
                    
            except Exception as e:
                self.logger.error(
                    f"Wrap-up workflow failed: {str(e)}",
                    context={"date": date, "task_id": self.current_task.get('task_id')},
                    exception=e,
                    print_console=True
                )

        # Clean up task-level sandbox to prevent accumulation
        # This ensures sandbox is killed after each task/day, not just at program exit
        try:
            from livebench.tools.productivity.code_execution_sandbox import SessionSandbox
            session_sandbox = SessionSandbox.get_instance()
            if session_sandbox.sandbox:
                session_sandbox.cleanup()
                self.logger.terminal_print("🧹 Cleaned up task sandbox")
        except Exception as e:
            self.logger.warning(
                f"Failed to cleanup task sandbox: {str(e)}",
                context={"date": date},
                print_console=False
            )

        # Record per-task completion statistics (only when work was actually submitted)
        if self.current_task and not session_api_error and self.last_work_submitted:
            wall_clock_seconds = (datetime.now() - task_start_dt).total_seconds()
            self.economic_tracker.record_task_completion(
                task_id=self.current_task['task_id'],
                work_submitted=self.last_work_submitted,
                wall_clock_seconds=wall_clock_seconds,
                evaluation_score=self.last_evaluation_score,
                money_earned=self.daily_work_income,
                attempt=self.current_attempt,
                date=date,
            )

        # End of day: save economic state
        self.economic_tracker.save_daily_state(
            date=date,
            work_income=self.daily_work_income,
            trading_profit=self.daily_trading_profit,
            api_error=session_api_error
        )
        
        # Clean up E2B sandbox for this session
        try:
            from livebench.tools.productivity.code_execution_sandbox import cleanup_session_sandbox
            cleanup_session_sandbox()
        except Exception as e:
            self.logger.warning(
                f"Failed to cleanup E2B sandbox: {str(e)}",
                context={"date": date},
                print_console=False
            )

        print(f"\n{'='*60}")
        print(f"📊 Daily Summary - {date}")
        print(f"   Balance: ${self.economic_tracker.get_balance():.2f}")
        print(f"   Daily Cost: ${self.economic_tracker.get_daily_cost():.2f}")
        print(f"   Work Income: ${self.daily_work_income:.2f}")
        print(f"   Trading P&L: ${self.daily_trading_profit:.2f}")
        print(f"   Status: {self.economic_tracker.get_survival_status()}")
        print(f"{'='*60}\n")

        if session_api_error:
            return "API_ERROR"

    def _load_already_done(self) -> tuple:
        """
        Read task_completions.jsonl to find dates and task IDs already conducted
        in a previous run.  Returns (already_done_dates: set[str], already_used_task_ids: set[str]).

        task_completions.jsonl is the source of truth: entries are only written for
        sessions that completed without an API error, so everything in it is "done".

        Also pre-populates task_manager.used_tasks and task_manager.daily_tasks so
        previously completed tasks are never re-assigned to new dates.
        """
        already_done_dates: set = set()
        already_used_task_ids: set = set()

        completions_file = os.path.join(self.data_path, "economic", "task_completions.jsonl")
        if not os.path.exists(completions_file):
            return already_done_dates, already_used_task_ids

        with open(completions_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    date = rec.get("date")
                    task_id = rec.get("task_id")
                    if date:
                        already_done_dates.add(date)
                    if task_id:
                        already_used_task_ids.add(task_id)
                        self.task_manager.used_tasks.add(task_id)
                        if date:
                            self.task_manager.daily_tasks[date] = task_id
                except (json.JSONDecodeError, KeyError):
                    pass

        return already_done_dates, already_used_task_ids

    async def run_date_range(self, init_date: str, end_date: str) -> None:
        """
        Run simulation for date range

        Args:
            init_date: Start date
            end_date: End date
        """
        print(f"\n🎮 Starting Simulation")
        print(f"   Agent: {self.signature}")
        print(f"   Model: {self.basemodel}")
        print(f"   Date Range: {init_date} to {end_date}")
        print(f"   Starting Balance: ${self.economic_tracker.initial_balance:.2f}\n")

        from datetime import datetime as dt, timedelta

        # Load already-processed dates so we never re-run or overwrite them
        already_done_dates, already_used_task_ids = self._load_already_done()
        if already_done_dates:
            print(f"♻️  Resuming — {len(already_done_dates)} date(s) already completed, "
                  f"skipping them.")
            print(f"   ({len(already_used_task_ids)} task(s) marked as used in task manager)\n")

        current_date = dt.strptime(init_date, "%Y-%m-%d")
        end = dt.strptime(end_date, "%Y-%m-%d")

        day_count = 0
        while current_date <= end:
            if current_date.weekday() < 5:  # Weekdays only
                date_str = current_date.strftime("%Y-%m-%d")

                if date_str in already_done_dates:
                    print(f"⏭️  Skipping {date_str} — already completed in a previous run")
                    current_date += timedelta(days=1)
                    continue

                day_count += 1
                result = await self.run_daily_session(date_str)

                # Evolution hook (Plan A): after a successful day with a task, optionally run Learn+Run2 and promote to main store
                if result is not None:
                    self.logger.terminal_print(f"   [evolution] Skip: session result is {result!r} (need None to check evolution)")
                elif not getattr(self, "current_task", None):
                    self.logger.terminal_print("   [evolution] Skip: no current_task")
                elif not getattr(self, "evolution_config", {}).get("enabled"):
                    self.logger.terminal_print("   [evolution] Skip: evolution.enabled is false")
                else:
                    try:
                        task_id = (self.current_task.get("task_id") or "").strip()
                        if task_id.startswith("learn-") or self.current_task.get("learn_only"):
                            self.logger.terminal_print(f"   [evolution] Skip evolution for learn-only task_id={task_id}")
                        else:
                            from pathlib import Path as _PathLib
                            _root = _PathLib(__file__).resolve().parents[2]
                            if str(_root) not in sys.path:
                                sys.path.insert(0, str(_root))
                            from scripts.single_task_evolve import (
                                get_run1_result_from_agent_path,
                                _should_evolve_reason,
                                run_evolution_for_task,
                            )
                            run1_result = get_run1_result_from_agent_path(
                                self.data_path,
                                date_str,
                                self.current_task.get("task_id", ""),
                                self.signature,
                            )
                            thr = getattr(self, "evolution_config", {}).get("threshold", 0.6)
                            should_run, reason = _should_evolve_reason(run1_result, thr)
                            self.logger.terminal_print(
                                f"   [evolution] run1_result: work_submitted={run1_result.get('work_submitted')}, "
                                f"score_0_1={run1_result.get('evaluation_score_0_1')}, earned={run1_result.get('money_earned')}, "
                                f"feedback_len={len(run1_result.get('feedback') or '')}"
                            )
                            self.logger.terminal_print(f"   [evolution] should_evolve={should_run}: {reason}")
                            if should_run:
                                self.logger.terminal_print("\n" + "=" * 60)
                                self.logger.terminal_print(f"   🧬 EVOLUTION 启动 [{date_str}] — 将执行 Learn 阶段 → Run2 阶段 → 技能提升至主目录")
                                self.logger.terminal_print("=" * 60)
                                run_evolution_for_task(
                                    self,
                                    date_str,
                                    self.current_task,
                                    run1_result,
                                    getattr(self, "evolution_config", {}),
                                    getattr(self, "evolution_config_path", "") or "",
                                )
                                self.logger.terminal_print("=" * 60)
                                self.logger.terminal_print(f"   🧬 EVOLUTION 结束 [{date_str}] — Learn + Run2 已完成，主流程继续")
                                self.logger.terminal_print("=" * 60 + "\n")
                    except Exception as e:
                        self.logger.terminal_print(f"   [evolution] Hook failed: {e}")
                        import traceback
                        traceback.print_exc()

                # Check if no tasks available
                if result == "NO_TASKS_AVAILABLE":
                    print(f"\n🛑 SIMULATION ENDED - No more tasks available on {date_str}")
                    print(f"   Completed: {day_count} days")
                    print(f"   All available tasks have been assigned")
                    break

                # Check bankruptcy
                if self.economic_tracker.is_bankrupt():
                    print(f"\n💀 GAME OVER - Agent {self.signature} went bankrupt on {date_str}")
                    print(f"   Survived: {day_count} days")
                    break

            current_date += timedelta(days=1)

        # Final summary
        self._print_final_summary(day_count)

    async def run_exhaust_mode(self, init_date: str, max_task_failures: int = 10) -> None:
        """
        Exhaust mode: attempt every available GDPVal task, retrying API errors up to
        max_task_failures times per task. Date advances by one weekday for each attempt,
        regardless of the config's end_date.

        A task is considered "conducted" once run_daily_session returns without an API_ERROR
        (even if the agent didn't submit work or scored below threshold). Retries are only
        triggered by API_ERROR (network/quota failures), not by evaluation failures.

        Stops when every task has been either conducted or exhausted max_task_failures retries.

        Args:
            init_date: Start date (YYYY-MM-DD); taken from config's date_range.init_date
            max_task_failures: Max API-error retries per task before skipping (default 10)
        """
        print(f"\n🎮 Starting Exhaust Mode")
        print(f"   Agent: {self.signature}")
        print(f"   Model: {self.basemodel}")
        print(f"   Start Date: {init_date}")
        print(f"   Max API Failures Per Task: {max_task_failures}")
        print(f"   Starting Balance: ${self.economic_tracker.initial_balance:.2f}\n")

        from datetime import datetime as dt, timedelta

        all_task_ids = self.task_manager.get_all_task_ids()
        if not all_task_ids:
            print("❌ No tasks available to exhaust")
            return

        total_tasks = len(all_task_ids)

        # --- Resume support: skip tasks already recorded in task_completions.jsonl ---
        completions_file = os.path.join(
            self.data_path, "economic", "task_completions.jsonl"
        )
        already_recorded: set = set()
        last_recorded_date: Optional[str] = None
        if os.path.exists(completions_file):
            with open(completions_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                        tid = rec.get("task_id")
                        if tid:
                            already_recorded.add(tid)
                        d = rec.get("date")
                        if d and (last_recorded_date is None or d > last_recorded_date):
                            last_recorded_date = d
                    except (json.JSONDecodeError, KeyError):
                        pass

        if already_recorded:
            print(f"♻️  Resuming exhaust run — {len(already_recorded)} task(s) already "
                  f"recorded in task_completions.jsonl, skipping them.")
            if last_recorded_date:
                print(f"   Last recorded date: {last_recorded_date}")

        print(f"📋 Total tasks: {total_tasks}  |  Already done: {len(already_recorded)}  "
              f"|  Remaining: {total_tasks - len(already_recorded)}\n")

        # Per-task failure counter; tasks not yet in the dict have 0 failures
        task_failures: Dict[str, int] = {}
        # Tasks that have been conducted (no API error).
        # task_completions.jsonl only records successful sessions, so everything
        # in already_recorded counts as conducted.
        task_conducted: set = set(already_recorded)
        # Tasks abandoned due to repeated API errors
        task_abandoned: set = set()

        # Build pending queue from tasks NOT yet recorded
        pending_queue: List[str] = [
            tid for tid in all_task_ids if tid not in already_recorded
        ]

        # Advance start date past the last recorded date so we never reuse a date
        # that already has balance / cost records from a previous run.
        if last_recorded_date:
            resume_date = dt.strptime(last_recorded_date, "%Y-%m-%d") + timedelta(days=1)
            current_date = resume_date
        else:
            current_date = dt.strptime(init_date, "%Y-%m-%d")
        total_attempts = 0

        while pending_queue:
            task_id = pending_queue.pop(0)
            attempt_num = task_failures.get(task_id, 0) + 1

            # Advance to next weekday
            while current_date.weekday() >= 5:
                current_date += timedelta(days=1)
            date_str = current_date.strftime("%Y-%m-%d")
            total_attempts += 1

            conducted = len(task_conducted)   # includes already_recorded from prior runs
            abandoned = len(task_abandoned)
            remaining = len(pending_queue)
            print(f"\n{'='*60}")
            print(f"🔄 Exhaust Attempt #{total_attempts}  |  Task: {task_id}")
            print(f"   Date: {date_str}  |  Attempt: {attempt_num}/{max_task_failures}")
            print(f"   Conducted: {conducted}/{total_tasks}  |  "
                  f"Abandoned: {abandoned}  |  Remaining: {remaining}")
            print(f"{'='*60}")

            # Force-assign this specific task to today's date so run_daily_session picks it
            task = self.task_manager.force_assign_task(task_id, date_str, self.signature)
            if not task:
                print(f"❌ Task {task_id} not found in dataset — skipping permanently")
                task_abandoned.add(task_id)
                current_date += timedelta(days=1)
                continue

            # Set attempt counter (used by record_task_completion)
            self.current_attempt = attempt_num

            result = await self.run_daily_session(date_str)

            if result == "API_ERROR":
                failures = task_failures.get(task_id, 0) + 1
                task_failures[task_id] = failures
                if failures < max_task_failures:
                    print(f"⚠️  API error on task {task_id} "
                          f"(attempt {attempt_num}, {max_task_failures - failures} retries left)")
                    pending_queue.append(task_id)  # Re-queue for later retry
                else:
                    print(f"❌ Task {task_id} abandoned after {max_task_failures} API errors")
                    task_abandoned.add(task_id)
            else:
                # Conducted regardless of evaluation outcome (result is None when session ended without API_ERROR)
                task_conducted.add(task_id)
                print(f"✅ Task {task_id} conducted (attempt {attempt_num})")

                # Evolution hook: run when result is None (session completed), current_task set, evolution.enabled True
                if result is not None:
                    self.logger.terminal_print(f"   [evolution] Skip: session result is {result!r} (need None to check evolution)")
                elif not getattr(self, "current_task", None):
                    self.logger.terminal_print("   [evolution] Skip: no current_task")
                elif not getattr(self, "evolution_config", {}).get("enabled"):
                    self.logger.terminal_print("   [evolution] Skip: evolution.enabled is false")
                else:
                    try:
                        task_id = (self.current_task.get("task_id") or "").strip()
                        if task_id.startswith("learn-") or self.current_task.get("learn_only"):
                            self.logger.terminal_print(f"   [evolution] Skip evolution for learn-only task_id={task_id}")
                        else:
                            from pathlib import Path as _PathLib
                            _root = _PathLib(__file__).resolve().parents[2]
                            if str(_root) not in sys.path:
                                sys.path.insert(0, str(_root))
                            from scripts.single_task_evolve import (
                                get_run1_result_from_agent_path,
                                _should_evolve_reason,
                                run_evolution_for_task,
                            )
                            run1_result = get_run1_result_from_agent_path(
                                self.data_path,
                                date_str,
                                self.current_task.get("task_id", ""),
                                self.signature,
                            )
                            thr = getattr(self, "evolution_config", {}).get("threshold", 0.6)
                            should_run, reason = _should_evolve_reason(run1_result, thr)
                            self.logger.terminal_print(
                                f"   [evolution] run1_result: work_submitted={run1_result.get('work_submitted')}, "
                                f"score_0_1={run1_result.get('evaluation_score_0_1')}, earned={run1_result.get('money_earned')}, "
                                f"feedback_len={len(run1_result.get('feedback') or '')}"
                            )
                            self.logger.terminal_print(f"   [evolution] should_evolve={should_run}: {reason}")
                            if should_run:
                                self.logger.terminal_print("\n" + "=" * 60)
                                self.logger.terminal_print(f"   🧬 EVOLUTION 启动 [{date_str}] — 将执行 Learn 阶段 → Run2 阶段 → 技能提升至主目录")
                                self.logger.terminal_print("=" * 60)
                                run_evolution_for_task(
                                    self,
                                    date_str,
                                    self.current_task,
                                    run1_result,
                                    getattr(self, "evolution_config", {}),
                                    getattr(self, "evolution_config_path", "") or "",
                                )
                                self.logger.terminal_print("=" * 60)
                                self.logger.terminal_print(f"   🧬 EVOLUTION 结束 [{date_str}] — Learn + Run2 已完成，主流程继续下一任务")
                                self.logger.terminal_print("=" * 60 + "\n")
                    except Exception as e:
                        self.logger.terminal_print(f"   [evolution] Hook failed: {e}")
                        import traceback
                        traceback.print_exc()

            if self.economic_tracker.is_bankrupt():
                print(f"\n💀 BANKRUPT on {date_str} — stopping exhaust mode")
                break

            current_date += timedelta(days=1)
            if pending_queue:
                self.logger.terminal_print(f"   ➡️  Next: {len(pending_queue)} task(s) remaining in queue.")

        # Reset attempt counter
        self.current_attempt = 1

        print(f"\n{'='*60}")
        print(f"🏁 EXHAUST MODE COMPLETE — {self.signature}")
        print(f"{'='*60}")
        print(f"   Total GDPVal tasks:  {total_tasks}")
        print(f"   Conducted:           {len(task_conducted)}")
        print(f"   Abandoned (errors):  {len(task_abandoned)}")
        print(f"   Total attempts:      {total_attempts}")
        print(f"{'='*60}\n")
        self._print_final_summary(total_attempts)

    def _print_final_summary(self, days_survived: int) -> None:
        """Print final simulation summary"""
        summary = self.economic_tracker.get_summary()

        print(f"\n{'='*60}")
        print(f"🏁 FINAL SUMMARY - {self.signature}")
        print(f"{'='*60}")
        print(f"   Days Survived: {days_survived}")
        print(f"   Final Balance: ${summary['balance']:.2f}")
        print(f"   Net Worth: ${summary['net_worth']:.2f}")
        print(f"   Total Token Cost: ${summary['total_token_cost']:.2f}")
        print(f"   Total Work Income: ${self.economic_tracker.total_work_income:.2f}")
        print(f"   Total Trading P&L: ${self.economic_tracker.total_trading_profit:.2f}")
        print(f"   Final Status: {summary['survival_status'].upper()}")
        print(f"{'='*60}\n")

    def __str__(self) -> str:
        return f"LiveAgent(signature='{self.signature}', model='{self.basemodel}')"
