"""
Direct LangChain tool wrappers (no MCP)

Core tools: decide_activity, submit_work, learn, get_status
Productivity tools: Imported from livebench.tools.productivity
"""

from langchain_core.tools import tool
from typing import Dict, Any, Union, Optional, List
import json
import os
from datetime import datetime

from livebench.utils.logger import get_logger


def _resolve_artifact_path(file_path: str, data_path: Optional[str] = None) -> Optional[str]:
    """
    Resolve a single artifact path to an existing file in a platform-agnostic way.
    - Normalizes slashes and redundant segments (e.g. a\\\\b -> platform form).
    - Tries: as-is, then relative to data_path, then relative to cwd.
    Returns the first path that exists and is a file, or None.
    """
    if not file_path or not isinstance(file_path, str):
        return None
    s = file_path.strip()
    if not s:
        return None
    normalized = os.path.normpath(s)
    candidates: List[str] = [normalized]
    if data_path:
        candidates.append(os.path.normpath(os.path.join(data_path, normalized)))
    if not os.path.isabs(normalized):
        candidates.append(os.path.normpath(os.path.abspath(normalized)))
    try:
        from livebench.utils.path_io import path_for_io
    except Exception:
        path_for_io = None
    for p in candidates:
        if not p:
            continue
        p_io = path_for_io(p) if path_for_io else p
        if os.path.exists(p_io) and os.path.isfile(p_io):
            return p_io
    return None


# Paths that exist only inside E2B sandbox; submit_work runs on host and must not accept these
_E2B_PATH_PREFIXES = ("/tmp/", "/tmp\\", "/home/user/", "/home/user\\", "\\tmp\\", "\\home\\user\\")


def _is_e2b_sandbox_path(path: str) -> bool:
    """True if path looks like an E2B sandbox path (not valid on host)."""
    if not path or not isinstance(path, str):
        return False
    p = path.strip().replace("\\", "/")
    return any(p.startswith(prefix.replace("\\", "/")) for prefix in _E2B_PATH_PREFIXES)


# Concatenated path: host sandbox path + E2B segment (e.g. .../sandbox/2025-01-15/home/user/livebench_work/file.xlsx)
_CONCAT_PATH_MARKERS = ("/home/user/", "\\home\\user\\", "/livebench_work/", "\\livebench_work\\")


def _is_concatenated_sandbox_path(path: str) -> bool:
    """True if path looks like sandbox path concatenated with E2B path segment (invalid on host)."""
    if not path or not isinstance(path, str):
        return False
    p = path.strip().replace("\\", "/")
    return any(marker.replace("\\", "/") in p for marker in _CONCAT_PATH_MARKERS)


def _e2b_rejection_response(e2b_paths: list) -> Dict[str, Any]:
    """Return the standard error response when agent passes E2B paths and no session fallback is available."""
    return {
        "error": (
            "artifact_file_paths must be HOST paths (from execute_code result's 'downloaded_artifacts' or create_file result's 'file_path'). "
            "Paths like /tmp/... or /home/user/... are E2B sandbox paths and do not exist on the host. "
            "After each execute_code that creates files, use submit_work(artifact_file_paths=result['downloaded_artifacts']) with that result's list; do not pass paths printed inside the sandbox."
        ),
        "rejected_e2b_paths": e2b_paths[:10],
    }


# Global state (will be set by agent)
_global_state = {}


def set_global_state(
    signature: str,
    economic_tracker: Any,
    task_manager: Any,
    evaluator: Any,
    current_date: str,
    current_task: Dict,
    data_path: str,
    supports_multimodal: bool = True,
    use_builtin_skills: bool = True,
):
    """Set global state for tools. use_builtin_skills: when True, skill tools merge global built-in skills with agent store."""
    global _global_state
    _global_state = {
        "signature": signature,
        "economic_tracker": economic_tracker,
        "task_manager": task_manager,
        "evaluator": evaluator,
        "current_date": current_date,
        "current_task": current_task,
        "data_path": data_path,
        "supports_multimodal": supports_multimodal,
        "use_builtin_skills": use_builtin_skills,
        "session_artifact_paths": [],  # accumulated from execute_code downloads and create_file; used as fallback when submit_work gets no paths
    }


@tool
def decide_activity(activity: str, reasoning: str) -> Dict[str, Any]:
    """
    Decide your daily activity: work or learn.

    Args:
        activity: Must be "work" or "learn"
        reasoning: Explanation for your decision (at least 50 characters)

    Returns:
        Dictionary with decision result
    """
    activity = activity.lower().strip()

    if activity not in ["work", "learn"]:
        return {
            "error": "Invalid activity. Must be 'work' or 'learn'",
            "valid_options": ["work", "learn"]
        }

    if len(reasoning) < 50:
        return {
            "error": "Reasoning must be at least 50 characters",
            "current_length": len(reasoning)
        }

    return {
        "success": True,
        "activity": activity,
        "reasoning": reasoning,
        "message": f"✅ Decision made: {activity.upper()}"
    }


@tool
def submit_work(work_output: str = "", artifact_file_paths: Union[list, str, None] = None) -> Dict[str, Any]:
    """
    Submit completed work for evaluation and payment.

    **Hard requirement (self-check closure):** You MUST perform a detailed self-check against the task requirements (e.g. use read_file to verify generated artifacts contain all required content/values) before calling submit_work. If self-check finds anything missing or wrong, you MUST fix it and re-verify; only when verification passes may you call submit_work. Do not submit when issues found during self-check have not been fixed and re-verified.

    Args:
        work_output: Your completed work as text (detailed answer to the task). 
                     Minimum 100 characters if no artifact_file_paths provided.
        artifact_file_paths: Use result['downloaded_artifacts'] from execute_code or result['file_path'] from create_file. Do not concatenate paths; do not use /tmp/ or /home/user/ paths.

    Returns:
        Dictionary with evaluation result and payment
        
    Examples:
        # Submit text answer only
        submit_work(work_output="My detailed analysis of...")
        
        # Submit files: use the list from execute_code result (not /tmp or /home/user paths)
        result = execute_code_sandbox(code="... print('ARTIFACT_PATH:/tmp/report.xlsx') ...")
        submit_work(artifact_file_paths=result['downloaded_artifacts'])
        
        # Submit both text and files
        submit_work(work_output="Here is my analysis...", artifact_file_paths=result['downloaded_artifacts'])
    """
    logger = get_logger()
    
    # Normalize artifact_file_paths - handle both list and JSON string formats
    if artifact_file_paths is None:
        artifact_file_paths = []
    elif isinstance(artifact_file_paths, str):
        # Handle JSON string representation of list
        try:
            parsed = json.loads(artifact_file_paths)
            if isinstance(parsed, list):
                artifact_file_paths = parsed
                if logger:
                    logger.info(
                        "Converted JSON string to list for artifact_file_paths",
                        context={"count": len(artifact_file_paths)},
                        print_console=False
                    )
            else:
                return {
                    "error": f"artifact_file_paths must be a list, got {type(parsed).__name__} after parsing JSON"
                }
        except json.JSONDecodeError as e:
            return {
                "error": f"artifact_file_paths is a string but not valid JSON: {str(e)}"
            }
    
    # Validate input - must have either work_output or artifact_file_paths
    if not work_output and not artifact_file_paths:
        if logger:
            logger.warning(
                "No work submitted",
                context={"has_output": bool(work_output), "has_files": bool(artifact_file_paths)},
                print_console=False
            )
        return {
            "error": "Must provide either work_output (text) or artifact_file_paths (files), or both"
        }
    
    # Validate work_output length if no files provided
    if work_output and not artifact_file_paths and len(work_output) < 100:
        if logger:
            logger.warning(
                "Work output too short and no files provided",
                context={"length": len(work_output), "required": 100},
                print_console=False
            )
        return {
            "error": "Work output too short. Minimum 100 characters required when not submitting files.",
            "current_length": len(work_output)
        }

    # Reject E2B sandbox paths, or auto-fix using session_artifact_paths when possible (stability)
    if artifact_file_paths:
        e2b_paths = [p for p in artifact_file_paths if _is_e2b_sandbox_path(p)]
        if e2b_paths:
            session_paths = _global_state.get("session_artifact_paths") or []
            if session_paths:
                # Build host path lookup by basename (from previous execute_code downloads)
                session_by_basename = {}
                for hp in session_paths:
                    if not isinstance(hp, str):
                        continue
                    b = os.path.basename(hp)
                    if b not in session_by_basename:
                        try:
                            if os.path.exists(hp) and os.path.isfile(hp):
                                session_by_basename[b] = hp
                        except Exception:
                            pass
                # Replace E2B paths with matched host paths so submission can proceed
                corrected = []
                all_matched = True
                for p in artifact_file_paths:
                    if _is_e2b_sandbox_path(p):
                        b = os.path.basename(p)
                        if b in session_by_basename:
                            corrected.append(session_by_basename[b])
                        else:
                            all_matched = False
                            break
                    else:
                        corrected.append(p)
                if all_matched and corrected:
                    artifact_file_paths = corrected
                    if logger:
                        logger.info(
                            "submit_work: agent passed E2B paths; used session_artifact_paths (matched by filename) so submission can proceed.",
                            context={"replaced_count": len(e2b_paths), "paths": [os.path.basename(x) for x in corrected[:5]]},
                            print_console=True,
                        )
                else:
                    return _e2b_rejection_response(e2b_paths)
            else:
                return _e2b_rejection_response(e2b_paths)
        if artifact_file_paths:
            concat_paths = [p for p in artifact_file_paths if _is_concatenated_sandbox_path(p)]
        if concat_paths:
            return {
                "error": (
                    "Do not concatenate paths. Use exactly result['downloaded_artifacts'] from the execute_code that created the files. "
                    "Paths containing 'home/user' or 'livebench_work' in the middle are invalid."
                ),
                "rejected_concatenated_paths": concat_paths[:10],
            }
    # Get global state
    evaluator = _global_state.get("evaluator")
    task = _global_state.get("current_task")
    date = _global_state.get("current_date")
    signature = _global_state.get("signature")
    economic_tracker = _global_state.get("economic_tracker")
    data_path = _global_state.get("data_path")

    if not task:
        # Log detailed debug info about global state
        if logger:
            logger.error(
                "No task assigned - global state issue",
                context={
                    "has_evaluator": evaluator is not None,
                    "has_date": date is not None,
                    "has_signature": signature is not None,
                    "has_tracker": economic_tracker is not None,
                    "has_data_path": data_path is not None,
                    "current_date": date,
                    "signature": signature,
                    "global_state_keys": list(_global_state.keys())
                },
                print_console=True
            )
        return {"error": "No task assigned for today"}

    # Fallback: if agent passed no artifact paths, use session-accumulated paths (from execute_code downloads and create_file)
    if not artifact_file_paths and _global_state.get("session_artifact_paths"):
        artifact_file_paths = list(_global_state["session_artifact_paths"])
        if logger:
            logger.info(
                "submit_work: using session_artifact_paths fallback",
                context={"count": len(artifact_file_paths)},
                print_console=False,
            )

    # Prepare artifact paths list
    all_artifact_paths = []
    
    # Save work_output to file if provided
    if work_output:
        work_dir = os.path.join(data_path, "work")
        os.makedirs(work_dir, exist_ok=True)

        # Create text artifact file (path_for_io for Windows long path)
        text_artifact_path = os.path.join(work_dir, f"{date}_{task['task_id']}.txt")
        try:
            from livebench.utils.path_io import path_for_io
            text_artifact_path_io = path_for_io(text_artifact_path) or text_artifact_path
        except Exception:
            text_artifact_path_io = text_artifact_path
        with open(text_artifact_path_io, "w", encoding="utf-8") as f:
            f.write(work_output)
        all_artifact_paths.append(text_artifact_path_io)
        
        if logger:
            logger.info(
                "Text work artifact saved",
                context={"path": text_artifact_path, "length": len(work_output)},
                print_console=False
            )
    
    # Add provided file paths (resolve with normalized paths for portability)
    if artifact_file_paths:
        existing_files: List[str] = []
        missing_files: List[str] = []
        
        for file_path in artifact_file_paths:
            resolved = _resolve_artifact_path(file_path, data_path)
            if resolved:
                existing_files.append(resolved)
            else:
                missing_files.append(file_path)
        
        if missing_files:
            error_msg = f"Some artifact files not found: {missing_files}"
            if logger:
                logger.error(
                    "Artifact files missing",
                    context={"missing": missing_files, "existing": existing_files},
                    print_console=True
                )
            return {
                "error": error_msg,
                "missing_files": missing_files,
                "existing_files": existing_files
            }
        
        all_artifact_paths.extend(existing_files)
        
        if logger:
            logger.info(
                "File artifacts added",
                context={
                    "count": len(existing_files),
                    "files": [os.path.basename(f) for f in existing_files]
                },
                print_console=False
            )
    
    # Log submission
    if logger:
        logger.info(
            "Submitting work for evaluation",
            context={
                "task_id": task['task_id'],
                "total_artifacts": len(all_artifact_paths),
                "artifact_types": [os.path.splitext(f)[1] for f in all_artifact_paths]
            },
            print_console=False
        )
    
    # Build submission summary for agent feedback
    submission_summary = []
    submission_summary.append(f"📦 WORK SUBMISSION SUMMARY:")
    submission_summary.append(f"   Total artifacts: {len(all_artifact_paths)}")
    for i, path in enumerate(all_artifact_paths, 1):
        file_type = os.path.splitext(path)[1] or "text"
        file_size = os.path.getsize(path) if os.path.exists(path) else 0
        submission_summary.append(f"   {i}. {os.path.basename(path)} ({file_type}, {file_size} bytes)")

    # Detect learn-only evolution tasks: they should not change income or show payment logs.
    task_id = str(task.get("task_id") or "")
    is_learn_only = bool(task.get("learn_only")) or task_id.startswith("learn-")

    if is_learn_only:
        # For learn-only sessions, there is NO evaluator model call, NO payment,
        # and NO economic impact. We only check that artifacts exist and return
        # a simple success result with placeholder evaluation fields.
        accepted = True
        payment = 0.0
        evaluation_score = 0.0
        feedback = (
            "Learn-only skill submission accepted.\n\n"
            "- No model evaluation was run for this task.\n"
            "- Artifacts have been recorded as candidate skills for future runs.\n"
        )
        actual_payment = 0.0
    else:
        # Evaluate work with all artifacts using LLM-based evaluator
        accepted, payment, feedback, evaluation_score = evaluator.evaluate_artifact(
            signature=signature,
            task=task,
            artifact_path=all_artifact_paths,  # Pass list of all artifacts
            description=f"Work submission with {len(all_artifact_paths)} artifact(s)"
        )

        # Record payment with evaluation score threshold (applies cliff at 0.6)
        actual_payment = economic_tracker.add_work_income(
            amount=payment,
            task_id=task_id,
            evaluation_score=evaluation_score
        )

    result = {
        "accepted": accepted,
        "payment": payment,  # Raw payment from evaluator
        "actual_payment": actual_payment,  # Cliff-adjusted payment (respects 0.6 threshold)
        "feedback": feedback,
        "evaluation_score": evaluation_score,
        "artifact_paths": all_artifact_paths,  # Return list of all artifacts
        "submission_summary": "\n".join(submission_summary)
    }

    # Mark success:
    # - Normal work: success only when actual_payment > 0
    # - Learn-only: success when evaluation_score is present (no payment concept)
    if is_learn_only:
        result["success"] = True
    elif actual_payment > 0:
        result["success"] = True

    # Clear session artifacts after submit so they are not reused
    if "session_artifact_paths" in _global_state:
        _global_state["session_artifact_paths"] = []

    return result


@tool
def learn(topic: str, knowledge: str) -> Dict[str, Any]:
    """
    Learn something new and add it to your knowledge base.

    Args:
        topic: Topic or title of what you learned
        knowledge: Detailed knowledge content (at least 200 characters)

    Returns:
        Dictionary with learning result
    """
    if len(knowledge) < 200:
        return {
            "error": "Knowledge content too short. Minimum 200 characters required.",
            "current_length": len(knowledge)
        }

    signature = _global_state.get("signature")
    date = _global_state.get("current_date")
    data_path = _global_state.get("data_path")

    # Save to learning memory
    memory_dir = os.path.join(data_path, "memory")
    os.makedirs(memory_dir, exist_ok=True)

    memory_file = os.path.join(memory_dir, "memory.jsonl")

    entry = {
        "date": date,
        "timestamp": datetime.now().isoformat(),
        "topic": topic,
        "knowledge": knowledge
    }

    with open(memory_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    return {
        "success": True,
        "topic": topic,
        "knowledge_length": len(knowledge),
        "message": f"✅ Learned about: {topic}"
    }


@tool
def get_status() -> Dict[str, Any]:
    """
    Get your current economic status and balance.

    Returns:
        Dictionary with current status information
    """
    tracker = _global_state.get("economic_tracker")

    if not tracker:
        return {"error": "Economic tracker not available"}

    return {
        "balance": tracker.get_balance(),
        "net_worth": tracker.get_net_worth(),
        "daily_cost": tracker.get_daily_cost(),
        "status": tracker.get_survival_status()
    }


# Import productivity tools from separate modules (if available)
try:
    from livebench.tools.productivity import (
        search_web as _search_web_original,
        create_file,
        execute_code_sandbox,
        read_file,
        create_video,
        read_webpage as _read_webpage_original
    )
    # At least one productivity tool must be loaded (search_web is always expected)
    PRODUCTIVITY_TOOLS_AVAILABLE = _search_web_original is not None
    if not PRODUCTIVITY_TOOLS_AVAILABLE:
        print("⚠️ Productivity tools not available (livebench.tools.productivity not loaded)")
except ImportError as e:
    _search_web_original = None
    create_file = None
    execute_code_sandbox = None
    read_file = None
    create_video = None
    _read_webpage_original = None
    PRODUCTIVITY_TOOLS_AVAILABLE = False
    print(f"⚠️ Productivity tools not available: {e}")


# Wrap search_web to track API costs (Tavily or Jina)
@tool
def search_web(query: str, max_results: int = 5, provider: str = None) -> Dict[str, Any]:
    """
    Search the internet for information using Tavily (default, with AI-generated answers) or Jina AI.

    Tavily provides structured results with AI-generated answers and relevance scores.
    Jina provides markdown-based results with titles, URLs, and snippets.

    Args:
        query: Search query string
        max_results: Maximum number of results to return (default: 5)
        provider: Search provider to use ("tavily" or "jina"). If not specified,
                 uses WEB_SEARCH_PROVIDER env var (defaults to "tavily")

    Returns:
        Dictionary with search results. Format depends on provider:

        Tavily: {"success": True, "provider": "tavily", "answer": "...", "results": [...], "images": [...]}
        Jina: {"success": True, "provider": "jina", "results": [...]}
    """
    if not PRODUCTIVITY_TOOLS_AVAILABLE:
        return {"error": "Search tool not available"}

    # Call original search_web with provider parameter
    result = _search_web_original.invoke({
        "query": query,
        "max_results": max_results,
        "provider": provider
    })

    # Track API cost if search was successful
    if isinstance(result, dict) and result.get("success"):
        try:
            tracker = _global_state.get("economic_tracker")
            if tracker:
                provider_used = result.get("provider", "unknown")

                if provider_used == "tavily":
                    # Tavily: Flat rate of $0.0008 per call
                    cost = tracker.track_flat_api_call(
                        cost=0.0008,
                        api_name="Tavily_Search"
                    )
                    result["api_cost"] = f"${cost:.6f}"
                    result["cost_type"] = "flat_rate"

                elif provider_used == "jina":
                    # Jina: Estimate tokens and charge at $0.05 per 1M tokens
                    result_text = str(result.get("results", ""))
                    estimated_tokens = len(result_text) // 4

                    cost = tracker.track_api_call(
                        tokens=estimated_tokens,
                        price_per_1m=0.05,
                        api_name="Jina_Search"
                    )
                    result["api_cost"] = f"${cost:.6f}"
                    result["estimated_tokens"] = estimated_tokens
                    result["cost_type"] = "per_token"

        except AttributeError as e:
            # Handle case where track_flat_api_call doesn't exist yet
            logger = get_logger()
            if logger:
                logger.warning(f"Economic tracker missing flat rate support, using fallback: {e}")

            # Fallback: Use track_api_call with fake tokens to achieve flat rate
            if result.get("provider") == "tavily":
                # $0.0008 per call = 16 tokens at $0.05 per 1M tokens
                fake_tokens = int(0.0008 * 1_000_000 / 0.05)
                cost = tracker.track_api_call(
                    tokens=fake_tokens,
                    price_per_1m=0.05,
                    api_name="Tavily_Search"
                )
                result["api_cost"] = f"${cost:.6f}"

        except Exception as e:
            # Don't fail the search if cost tracking fails
            logger = get_logger()
            if logger:
                logger.warning(f"Failed to track search API cost: {e}")

    return result


@tool
def read_webpage(urls: str, query: str = None) -> Dict[str, Any]:
    """Extract and read web page content from specified URLs using Tavily Extract.

    This tool extracts the main content from web pages, returning cleaned text
    in markdown format. Useful for reading articles, documentation, or any web content.

    Args:
        urls: Single URL or comma-separated list of URLs to extract content from
                 Example: "https://en.wikipedia.org/wiki/Artificial_intelligence"
        query: Optional query for reranking extracted content chunks based on relevance

    Returns:
        Dictionary with extracted web page content
    """
    if not PRODUCTIVITY_TOOLS_AVAILABLE:
        return {"error": "Webpage extraction tool not available"}

    # Call original read_webpage
    result = _read_webpage_original.invoke({
        "urls": urls,
        "query": query
    })

    # Track API cost if extraction was successful
    if isinstance(result, dict) and result.get("success"):
        try:
            tracker = _global_state.get("economic_tracker")
            if tracker:
                # Tavily Extract: Flat rate of $0.00016 per call (1 credit per 5 extractions)
                cost = tracker.track_flat_api_call(
                    cost=0.00016,
                    api_name="Tavily_Extract"
                )
                result["api_cost"] = f"${cost:.6f}"
                result["cost_type"] = "flat_rate"

        except AttributeError:
            # Fallback for older tracker versions
            logger = get_logger()
            if logger:
                logger.warning("Economic tracker missing flat rate support for webpage extraction")

            # Use track_api_call with fake tokens to achieve flat rate
            # $0.00016 per call = 3.2 tokens at $0.05 per 1M tokens
            fake_tokens = int(0.00016 * 1_000_000 / 0.05)
            cost = tracker.track_api_call(
                tokens=fake_tokens,
                price_per_1m=0.05,
                api_name="Tavily_Extract"
            )
            result["api_cost"] = f"${cost:.6f}"

        except Exception as e:
            logger = get_logger()
            if logger:
                logger.warning(f"Failed to track webpage extraction API cost: {e}")

    return result


def get_all_tools(
    skill_enabled: bool = False,
    *,
    allow_decide_activity: bool = True,
    allow_learn: bool = True,
):
    """Get list of all tools

    Args:
        skill_enabled: If True, append skill tools (get_skills, search_skills, get_skill_content).
                      Default False so existing callers keep current behavior.
        allow_decide_activity: If False, omit decide_activity tool (used when activity is forced by config).
        allow_learn: If False, omit learn tool (used to enforce "work every day").

    Returns:
    - core tools (decide_activity?, submit_work, learn?, get_status)
    - 6 productivity tools (search_web, read_webpage, create_file, execute_code_sandbox, read_file, create_video) if available
    - skill tools (get_skills, search_skills, get_skill_content) if skill_enabled
    """
    core_tools = []
    if allow_decide_activity:
        core_tools.append(decide_activity)
    core_tools.append(submit_work)
    if allow_learn:
        core_tools.append(learn)
    core_tools.append(get_status)

    if PRODUCTIVITY_TOOLS_AVAILABLE:
        productivity_tools = [
            t for t in [
                search_web,
                read_webpage,
                create_file,
                execute_code_sandbox,
                read_file,
                create_video
            ]
            if t is not None
        ]
        tools = core_tools + productivity_tools
    else:
        tools = core_tools

    if skill_enabled:
        try:
            from livebench.skill import get_skill_tools
            tools = tools + get_skill_tools()
        except ImportError:
            pass

    return tools
