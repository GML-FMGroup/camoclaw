"""
Start MCP Services - Direct Python execution
"""

import os
import sys
import subprocess
import time
from pathlib import Path

# Get project root (parent of camoclaw/)
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "camoclaw"))


def start_livebench_services():
    """Start MCP services using direct Python execution"""

    # Get ports from environment or use defaults
    livebench_port = os.getenv("LIVEBENCH_HTTP_PORT", "8010")

    script_path = project_root / "camoclaw" / "tools" / "tool_camoclaw.py"

    if not script_path.exists():
        print(f"❌ Script not found: {script_path}")
        sys.exit(1)

    print("🚀 Starting MCP services...")
    print("=" * 60)
    print(f"\n📡 Starting Tools on port {livebench_port}...")

    # Set environment variable for the port
    env = os.environ.copy()
    env["LIVEBENCH_HTTP_PORT"] = livebench_port

    # Try to start with mcp command first
    try:
        cmd = ["mcp", "run-http", str(script_path), "--port", livebench_port]
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env
        )

        # Wait a bit to see if it starts
        time.sleep(1)
        if process.poll() is None:
            print(f"✅ Tools started (PID: {process.pid})")
            print(f"   URL: http://localhost:{livebench_port}/mcp")

            # Keep running
            print("\n" + "=" * 60)
            print("✅ MCP services are running!")
            print(f"\nService URL: http://localhost:{livebench_port}/mcp")
            print("\n💡 Keep this terminal open while running the framework")
            print("Press Ctrl+C to stop all services")
            print("=" * 60)

            try:
                process.wait()
            except KeyboardInterrupt:
                print("\n\n🛑 Stopping services...")
                process.terminate()
                process.wait()
                print("✅ All services stopped")
            return
    except FileNotFoundError:
        print("⚠️  'mcp' command not found, trying direct Python execution...")

    # Fallback: Run directly with Python using fastmcp
    print("\n📦 Installing fastmcp if needed...")
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "fastmcp"], check=True)
    except:
        print("❌ Failed to install fastmcp")
        print("\nPlease install manually:")
        print("  pip install fastmcp")
        sys.exit(1)

    # Now run with fastmcp
    cmd = [sys.executable, "-m", "fastmcp", "run", str(script_path), "--transport", "streamable_http", "--port", livebench_port]

    try:
        process = subprocess.Popen(
            cmd,
            env=env
        )

        print(f"✅ Tools started (PID: {process.pid})")
        print(f"   URL: http://localhost:{livebench_port}/mcp")

        print("\n" + "=" * 60)
        print("✅ MCP services are running!")
        print(f"\nService URL: http://localhost:{livebench_port}/mcp")
        print("\n💡 Keep this terminal open while running the framework")
        print("Press Ctrl+C to stop all services")
        print("=" * 60)

        try:
            process.wait()
        except KeyboardInterrupt:
            print("\n\n🛑 Stopping services...")
            process.terminate()
            process.wait()
            print("✅ All services stopped")
    except Exception as e:
        print(f"❌ Failed to start Tools: {e}")
        sys.exit(1)


if __name__ == "__main__":
    start_livebench_services()

