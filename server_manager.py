import os
import subprocess
import time

import requests
import yaml


class LlamaServerManager:
    """Spawns and manages llama-server processes for each model under test.

    The server is started with --jinja so that the OpenAI-compatible
    /v1/chat/completions endpoint can emit tool_calls.
    """

    def __init__(self, config_path: str = "config.yaml"):
        with open(config_path) as f:
            self.config = yaml.safe_load(f)
        self.processes: dict[str, subprocess.Popen] = {}

    @staticmethod
    def _resolve_binary(explicit: str | None = None) -> str:
        """Find the llama-server binary, trying multiple candidate paths.

        Priority:
        1. Explicit config.yaml override
        2. shutil.which("llama-server")  (PATH)
        3. Common install / build directories
        """
        import shutil

        candidates = []
        if explicit:
            candidates.append(explicit)

        candidates.extend(
            [
                "llama-server",
                "/opt/homebrew/bin/llama-server",
                "/usr/local/bin/llama-server",
                "./build/bin/llama-server",
                "../build/bin/llama-server",
            ]
        )

        tried = []
        for path in candidates:
            resolved = shutil.which(path) if not os.path.isabs(path) else path
            tried.append(path)
            if resolved and os.path.isfile(resolved) and os.access(resolved, os.X_OK):
                return resolved

        raise RuntimeError(
            f"Could not find llama-server binary.\n"
            f"Tried: {', '.join(tried)}\n"
            f"Please install llama.cpp (e.g. brew install llama.cpp or build from source) "
            f"or set 'server_binary: /absolute/path/to/llama-server' in config.yaml."
        )

    def start(self, model_name: str):
        if model_name in self.processes:
            raise RuntimeError(f"Server for {model_name} is already running")

        model_cfg = self.config["models"][model_name]
        binary = self._resolve_binary(model_cfg.get("server_binary"))
        cmd = [
            binary,
            "--jinja",
            "-m",
            model_cfg["gguf_path"],
            "--port",
            str(model_cfg["port"]),
            "-c",
            str(model_cfg.get("context_size", 4096)),
        ]
        if "chat_template" in model_cfg:
            cmd.extend(["--chat-template", model_cfg["chat_template"]])
        if "chat_template_file" in model_cfg:
            cmd.extend(["--chat-template-file", model_cfg["chat_template_file"]])

        print(f"[server] Starting {' '.join(cmd)}")
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.processes[model_name] = proc

        # Poll /v1/models until the server is ready
        base_url = f"http://localhost:{model_cfg['port']}"
        for _attempt in range(60):
            try:
                r = requests.get(f"{base_url}/v1/models", timeout=2)
                if r.status_code == 200:
                    print(f"[server] {model_name} ready on {base_url}")
                    # Check tool support and warn if disabled
                    try:
                        props_r = requests.get(f"{base_url}/props", timeout=2)
                        if props_r.status_code == 200:
                            props = props_r.json()
                            caps = props.get("chat_template_caps", {})
                            if caps.get("supports_tools") is False:
                                print(
                                    f"[WARN] Server reports supports_tools=false for "
                                    f"{model_name}. Tool calling may not work."
                                )
                    except Exception:
                        pass
                    return
            except requests.exceptions.ConnectionError:
                pass
            time.sleep(1)
        raise RuntimeError(f"Server for {model_name} did not become ready in 60s")

    def stop(self, model_name: str):
        proc = self.processes.get(model_name)
        if proc is None:
            return
        print(f"[server] Stopping {model_name}")
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        del self.processes[model_name]

    def stop_all(self):
        for name in list(self.processes.keys()):
            self.stop(name)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop_all()
