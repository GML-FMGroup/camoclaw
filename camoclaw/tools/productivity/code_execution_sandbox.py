"""
Code execution tool with sandboxing
"""

from langchain_core.tools import tool
from typing import Dict, Any, Optional, List
from e2b_code_interpreter import Sandbox
import os
import re
from pathlib import Path
import time
from dotenv import load_dotenv

load_dotenv()

# Retry config for E2B artifact download (large files may timeout)
_ARTIFACT_DOWNLOAD_RETRIES = 3
_ARTIFACT_DOWNLOAD_RETRY_DELAY_SEC = 2

# Import global state from parent module
def _get_global_state():
    """Get global state from parent module"""
    from camoclaw.tools.direct_tools import _global_state
    return _global_state


# Session-level sandbox manager
class SessionSandbox:
    """
    Manages a persistent E2B sandbox for an agent session.
    This ensures files created in one execute_code call are accessible in subsequent calls.
    """
    _instance: Optional['SessionSandbox'] = None
    
    def __init__(self):
        self.sandbox: Optional[Sandbox] = None
        self.sandbox_id: Optional[str] = None
        self.uploaded_reference_files: Dict[str, str] = {}  # local_path -> remote_path
    
    @classmethod
    def get_instance(cls) -> 'SessionSandbox':
        """Get or create the singleton session sandbox instance"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    @classmethod
    def reset(cls):
        """Reset the session sandbox (for new sessions/days)"""
        if cls._instance and cls._instance.sandbox:
            try:
                cls._instance.sandbox.kill()  # Use kill() for immediate termination
            except:
                pass
        cls._instance = None
    
    def get_or_create_sandbox(self, timeout: int = 3600) -> Sandbox:  # Default 1 hour for task duration
        """Get existing sandbox or create a new one, with health check"""
        
        # Health check existing sandbox
        if self.sandbox is not None:
            try:
                # Quick health check - list root directory
                self.sandbox.files.list("/")
                return self.sandbox  # Sandbox is healthy
            except Exception as e:
                # Sandbox is dead, clean up and recreate
                print(f"⚠️ Sandbox {self.sandbox_id} died ({e}), recreating...")

                try:
                    self.sandbox.kill()  # Use kill() for immediate termination
                except:
                    pass
                
                self.sandbox = None
                self.sandbox_id = None
                self.uploaded_reference_files = {}
        
        # Create new sandbox if needed (use default template; "gdpval-workspace" is optional custom template)
        if self.sandbox is None:
            try:
                self.sandbox = Sandbox.create(timeout=timeout)
                self.sandbox_id = getattr(self.sandbox, "id", None)
                print(f"🔧 Created persistent E2B sandbox: {self.sandbox_id}")
            except Exception as e:
                raise RuntimeError(f"Failed to create E2B sandbox: {str(e)}")
        
        return self.sandbox
    
    def upload_reference_file(self, local_path: str, remote_dir: str = "/home/user/reference_files") -> Optional[str]:
        """
        Upload a reference file to the sandbox.

        Args:
            local_path: Path to local file
            remote_dir: Directory in sandbox to upload to

        Returns:
            Remote path in sandbox, or None if upload failed (e.g. E2B API 404).
            Reference files remain available locally for read_file().
        """
        from camoclaw.utils.path_io import path_for_io
        path_to_read = path_for_io(local_path) or local_path
        if not os.path.exists(path_to_read):
            raise FileNotFoundError(f"Reference file not found: {local_path}")
        
        # Check if already uploaded
        if local_path in self.uploaded_reference_files:
            print(f"♻️ Reference file already uploaded: {os.path.basename(local_path)}")
            return self.uploaded_reference_files[local_path]
        
        sandbox = self.get_or_create_sandbox()
        
        # Ensure remote directory exists by creating parent directories
        # E2B will create the directory structure if it doesn't exist
        print(f"📁 Ensuring directory exists: {remote_dir}")
        
        # Read file content (path_to_read supports Windows long path)
        with open(path_to_read, 'rb') as f:
            content = f.read()
        
        # Create remote path
        filename = os.path.basename(local_path)
        remote_path = f"{remote_dir}/{filename}"
        
        # Upload file - E2B will create parent directories automatically
        try:
            sandbox.files.write(remote_path, content)
            self.uploaded_reference_files[local_path] = remote_path
            print(f"✅ Uploaded reference file: {filename} -> {remote_path}")
            print(f"   📍 E2B Sandbox path: {remote_path}")
            print(f"   📦 File size: {len(content)} bytes")
            return remote_path
        except Exception as e:
            error_msg = str(e)
            print(f"⚠️ E2B upload failed for {filename}: {error_msg}")
            print(f"   Reference files are still available locally; use read_file() to read them. execute_code will not see them in /home/user/reference_files/.")
            # Do not raise: allow run to continue; agent can use read_file() for local reference files
            return None
    
    def download_artifact(self, remote_path: str, local_dir: str) -> str:
        """
        Download an artifact file from the sandbox to local storage
        
        Args:
            remote_path: Path in sandbox
            local_dir: Local directory to save to
            
        Returns:
            Local path of downloaded file
        """
        if not self.sandbox:
            raise RuntimeError("No active sandbox")
        
        try:
            # Read file content as bytes to prevent corruption of binary files (PNG, DOCX, XLSX, etc.)
            # E2B SDK: format="bytes" returns bytearray, format="text" returns str
            content_bytes = self.sandbox.files.read(remote_path, format="bytes")
            
            # Create local path (use normpath for portable, consistent paths across platforms)
            os.makedirs(local_dir, exist_ok=True)
            filename = os.path.basename(remote_path)
            local_path = os.path.normpath(os.path.join(local_dir, filename))
            from camoclaw.utils.path_io import path_for_io
            local_path_io = path_for_io(local_path) or local_path
            # Write content as binary (local_path_io supports Windows long path)
            with open(local_path_io, 'wb') as f:
                f.write(content_bytes)
            
            print(f"📥 Downloaded artifact: {remote_path} -> {local_path_io}")
            return local_path_io
        except Exception as e:
            raise RuntimeError(f"Failed to download {remote_path}: {str(e)}")
    
    def cleanup(self):
        """Kill the sandbox and clean up resources"""
        if self.sandbox:
            try:
                self.sandbox.kill()  # Use kill() for immediate termination
                print(f"🧹 Killed E2B sandbox: {self.sandbox_id}")
            except:
                pass
            self.sandbox = None
            self.sandbox_id = None
            self.uploaded_reference_files = {}


@tool
def execute_code(code: str, language: str = "python") -> Dict[str, Any]:
    """
    Execute code in a persistent E2B cloud sandbox with artifact download support.

    FEATURES:
    - Code runs in an isolated E2B Sandbox VM (separate from host)
    - Uses persistent sandbox per session (files persist across calls)
    - Currently restricted to Python code via E2B Python template
    - No direct access to host filesystem
    - API key based access control via E2B (requires E2B_API_KEY)
    - Automatically downloads files marked with ARTIFACT_PATH: prefix

    ARTIFACT DOWNLOAD:
    - To make files accessible to submit_work, include in your code:
      print("ARTIFACT_PATH:/path/to/file.ext")
    - Files are downloaded to the host; the result contains 'downloaded_artifacts' with host paths.
    - submit_work REJECTS /tmp/ and /home/user/... paths. You MUST pass artifact_file_paths=result['downloaded_artifacts'] from this call.
    - Example:
      result = execute_code('... print("ARTIFACT_PATH:/tmp/report.pdf") ...')
      submit_work(artifact_file_paths=result['downloaded_artifacts'])  # required

    Args:
        code: Code to execute
        language: Programming language - currently only "python" supported

    Returns:
        Dictionary with execution result (stdout, stderr, exit_code, downloaded_artifacts)
    """
    # Validate inputs
    if not code or len(code) < 1:
        return {"error": "Code cannot be empty"}

    language = language.lower().strip()
    if language != "python":
        return {
            "error": f"Language '{language}' not supported",
            "supported_languages": ["python"]
        }

    # Get global state for sandbox directory
    global_state = {}
    try:
        global_state = _get_global_state()
    except Exception:
        pass

    # Get or create persistent session sandbox
    session_sandbox = SessionSandbox.get_instance()
    
    try:
        sandbox = session_sandbox.get_or_create_sandbox(timeout=3600)  # 1 hour to match max task duration
        
        # Execute code
        try:
            # Ensure a stable working directory inside the sandbox so files are easier to find
            # and less likely to be lost when using relative paths.
            workdir = "/home/user/camoclaw_work"
            prelude = (
                "import os\n"
                f"os.makedirs({workdir!r}, exist_ok=True)\n"
                f"os.chdir({workdir!r})\n"
            )
            execution = sandbox.run_code(prelude + "\n" + code)
        except Exception as e:
            return {
                "success": False,
                "error": f"E2B sandbox execution failed: {str(e)}"
            }

        logs = getattr(execution, "logs", "")
        error = getattr(execution, "error", None)
        success = error is None
        
        # Extract stdout properly for artifact path detection
        if hasattr(logs, 'stdout'):
            stdout_str = '\n'.join(logs.stdout) if isinstance(logs.stdout, list) else str(logs.stdout)
        else:
            stdout_str = str(logs)
        
        # Parse ARTIFACT_PATH markers and download files
        downloaded_artifacts = []
        if success and "ARTIFACT_PATH:" in stdout_str:
            artifact_paths = re.findall(r'ARTIFACT_PATH:(\S+)', stdout_str)
            
            if artifact_paths and global_state.get("data_path"):
                # Determine local download directory (normpath for portable paths)
                current_date = global_state.get("current_date", "unknown")
                sandbox_dir = os.path.normpath(os.path.join(
                    global_state["data_path"],
                    "sandbox",
                    current_date,
                ))
                os.makedirs(sandbox_dir, exist_ok=True)
                
                # Download each artifact with retries (large files may timeout)
                for remote_path in artifact_paths:
                    last_error = None
                    for attempt in range(_ARTIFACT_DOWNLOAD_RETRIES):
                        try:
                            local_path = session_sandbox.download_artifact(remote_path, sandbox_dir)
                            downloaded_artifacts.append(local_path)
                            last_error = None
                            break
                        except Exception as e:
                            last_error = e
                            if attempt < _ARTIFACT_DOWNLOAD_RETRIES - 1:
                                time.sleep(_ARTIFACT_DOWNLOAD_RETRY_DELAY_SEC)
                    if last_error is not None:
                        print(f"⚠️ Warning: Could not download {remote_path} after {_ARTIFACT_DOWNLOAD_RETRIES} attempts: {last_error}")
        
        result = {
            "success": success,
            "exit_code": 0 if success else 1,
            "stdout": logs if success else "",
            "stderr": str(error) if error else "",
            "sandbox_id": session_sandbox.sandbox_id,
            "message": "✅ Code executed in E2B sandbox" if success else "❌ E2B sandbox execution reported an error",
            "workdir": "/home/user/camoclaw_work",
        }
        
        # If failed with ModuleNotFoundError, suggest pip install in code
        if not success and result.get("stderr") and ("ModuleNotFoundError" in result["stderr"] or "No module named" in result["stderr"]):
            result["message"] += "\n\n💡 Tip: The E2B sandbox may not have every package. Add at the start of your code: import subprocess; subprocess.check_call(['pip', 'install', 'PyPDF2'])  (or the missing package name)."

        # Add reference files info if available (manifest for path-design: use only these names in code)
        if session_sandbox.uploaded_reference_files:
            ref_names = [os.path.basename(r) for r in session_sandbox.uploaded_reference_files.values()]
            result["reference_file_names"] = ref_names
            result["message"] += f"\n\n📎 REFERENCE FILES AVAILABLE in E2B sandbox at /home/user/reference_files/:"
            for local_path, remote_path in session_sandbox.uploaded_reference_files.items():
                filename = os.path.basename(remote_path)
                result["message"] += f"\n  • {filename} at {remote_path}"
            result["message"] += "\n\n⚠️ In your code use ONLY these file names (e.g. /home/user/reference_files/<name>); names not in this list do not exist in the sandbox."
        
        # Add downloaded artifacts info
        if downloaded_artifacts:
            result["downloaded_artifacts"] = downloaded_artifacts
            result["message"] += f"\n\n📥 DOWNLOADED {len(downloaded_artifacts)} ARTIFACT(S) - Use these paths for submit_work:"
            for path in downloaded_artifacts:
                result["message"] += f"\n  ✅ {path}"
            result["message"] += f"\n\n⚠️ IMPORTANT: Use the paths above (not /tmp/ paths) when calling submit_work!"
            try:
                g = _get_global_state()
                g.setdefault("session_artifact_paths", []).extend(downloaded_artifacts)
            except Exception:
                pass
        else:
            # Common failure mode: files created in the sandbox aren't accessible to submit_work
            # unless explicitly downloaded. Provide a concise reminder.
            result["message"] += (
                "\n\n💡 Tip: If you create a file you want to submit, print "
                "\"ARTIFACT_PATH:/absolute/path/to/file\" so it will be downloaded "
                "to the local agent sandbox for submit_work."
            )
        
        return result
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Unexpected error during E2B sandbox execution: {str(e)}"
        }


def upload_task_reference_files(reference_file_paths: List[str]) -> List[str]:
    """
    Upload reference files to the persistent E2B sandbox.
    This should be called when a task is assigned to make reference files available.
    
    Args:
        reference_file_paths: List of local file paths to upload
        
    Returns:
        List of remote paths in the sandbox
    """
    if not reference_file_paths:
        return []
    
    print(f"\n📤 Uploading {len(reference_file_paths)} reference file(s) to E2B sandbox...")
    
    session_sandbox = SessionSandbox.get_instance()
    
    # Ensure sandbox is created before uploading
    sandbox = session_sandbox.get_or_create_sandbox()
    print(f"✅ E2B Sandbox ready (ID: {session_sandbox.sandbox_id})")
    
    remote_paths = []
    
    for i, local_path in enumerate(reference_file_paths, 1):
        try:
            print(f"\n[{i}/{len(reference_file_paths)}] Uploading: {os.path.basename(local_path)}")
            remote_path = session_sandbox.upload_reference_file(local_path)
            if remote_path is not None:
                remote_paths.append(remote_path)
        except Exception as e:
            print(f"❌ Failed to upload {local_path}: {e}")
    
    if remote_paths:
        print(f"\n✅ Successfully uploaded {len(remote_paths)}/{len(reference_file_paths)} files to E2B sandbox")
        print(f"📍 All files are accessible at: /home/user/reference_files/")
        print(f"   Files uploaded:")
        for path in remote_paths:
            print(f"     • {path}")
    else:
        print(f"\n⚠️ No files were successfully uploaded")
    
    return remote_paths


def cleanup_session_sandbox():
    """
    Clean up the session sandbox.
    Should be called at the end of each agent session/day.
    """
    SessionSandbox.reset()


if __name__ == "__main__":
    """
    Test the persistent sandbox functionality
    """
    def test1():
        # Test basic code execution
        test_code = """
print("Hello from E2B sandbox!")
for i in range(3):
    print("Number:", i)
        """

        result = execute_code.func(test_code, language="python")

        print("=== E2B Sandbox Execution Result ===")
        for k, v in result.items():
            print(f"{k}: {v}")
            
    def test2():
        # Test file persistence across calls
        test_code1 = """
with open("/tmp/test.txt", "w") as f:
    f.write("Hello from first call!")
print("ARTIFACT_PATH:/tmp/test.txt")
        """
        
        result1 = execute_code.func(test_code1, language="python")
        print("=== First Call Result ===")
        print(result1.get("message"))
        
        # Second call should be able to read the file
        test_code2 = """
with open("/tmp/test.txt", "r") as f:
    content = f.read()
print(f"File content: {content}")
        """
        
        result2 = execute_code.func(test_code2, language="python")
        print("\n=== Second Call Result ===")
        print(result2.get("stdout"))

    print("Running test 1: Basic execution")
    test1()
    
    print("\n" + "="*50)
    print("Running test 2: File persistence")
    test2()
    
    # Cleanup
    cleanup_session_sandbox()