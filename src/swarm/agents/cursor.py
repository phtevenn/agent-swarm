"""Adapter for Cursor Agent CLI (agent).

The `agent` command provides a headless coding agent with --print mode
for non-interactive use. Permission levels map to:
  full-auto  -> --yolo --trust  (execute everything without prompting)
  auto-edit  -> --trust         (default tool access, trust workspace)
  suggest    -> --mode plan     (read-only planning, no edits)
"""

from __future__ import annotations

import asyncio
import json

from swarm.config.schema import AgentConfig, AgentType, ApprovalMode

from .base import BaseAgent, WorkerNeedsFeedback

_APPROVAL_FLAGS: dict[ApprovalMode, list[str]] = {
    ApprovalMode.FULL_AUTO: ["--yolo", "--trust"],
    ApprovalMode.AUTO_EDIT: ["--trust"],
    ApprovalMode.SUGGEST: ["--mode", "plan", "--trust"],
    ApprovalMode.DEFAULT: [],
}


class CursorAgent(BaseAgent):
    """Wraps the `agent` CLI (Cursor Agent).

    Lead mode: conversational with --print and --continue for session continuity.
    Worker mode: one-shot --print for delegated tasks.
    """

    agent_type = AgentType.CURSOR

    def _build_cmd(self) -> list[str]:
        cmd = ["agent", "--print", "--output-format", "json"]
        cmd.extend(_APPROVAL_FLAGS.get(self.approval_mode, []))
        if self.config.model:
            cmd.extend(["--model", self.config.model])
        return cmd

    async def health_check(self) -> bool:
        try:
            await self._run_cli(["agent", "--version"])
            return True
        except Exception:
            return False

    async def send(
        self,
        message: str,
        system_prompt: str | None = None,
        continue_session: bool = False,
    ) -> str:
        cmd = self._build_cmd()
        if continue_session and self._session_started:
            cmd.append("--continue")
        cmd.append(message)

        raw = await self._run_cli(cmd)
        self._session_started = True
        return self._extract_result(raw)

    async def execute(self, task: str, context: str = "") -> str:
        prompt = f"{task}\n\n{context}" if context else task
        raw = await self._run_cli([*self._build_cmd(), prompt])
        return self._extract_result(raw)

    async def _run_cli_streaming(
        self, args: list[str], on_line=None, no_output_timeout=None
    ) -> str:
        """Stream agent output; parse JSON and forward only the 'result' field; support timeout and feedback."""
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self.work_dir,
        )
        reader = proc.stdout
        assert reader is not None
        lines: list[str] = []
        no_sec = no_output_timeout or 0
        try:
            while True:
                try:
                    raw_line = (
                        await asyncio.wait_for(reader.readline(), timeout=no_sec)
                        if no_sec > 0
                        else await reader.readline()
                    )
                except asyncio.TimeoutError:
                    proc.kill()
                    await proc.wait()
                    raise RuntimeError(
                        f"{args[0]} produced no output for {no_sec}s (killed)."
                    )
                if not raw_line:
                    break
                text = raw_line.decode(errors="replace").rstrip("\n")
                lines.append(text)
                if on_line:
                    readable = self._line_to_readable(text)
                    for part in readable.split("\n"):
                        out = on_line(part)
                        if isinstance(out, dict) and out.get("stop") and out.get("question"):
                            proc.kill()
                            await proc.wait()
                            raise WorkerNeedsFeedback(out["question"], self.name)
            await proc.wait()
            if proc.returncode != 0:
                stderr = (await proc.stderr.read()).decode().strip()
                raise RuntimeError(f"{args[0]} exited with code {proc.returncode}: {stderr}")
            return self._extract_result("\n".join(lines))
        except WorkerNeedsFeedback:
            raise
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
            raise

    def _line_to_readable(self, line: str) -> str:
        """If line is Cursor JSON with a result field, return that; else return line."""
        line = line.strip()
        if not line.startswith("{"):
            return line
        try:
            data = json.loads(line)
            if isinstance(data, dict):
                return data.get("result", data.get("text", line)) or line
        except json.JSONDecodeError:
            pass
        return line

    def _extract_result(self, raw: str) -> str:
        """Extract text from agent JSON output, falling back to raw string."""
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                return data.get("result", data.get("text", raw))
        except json.JSONDecodeError:
            pass
        return raw
