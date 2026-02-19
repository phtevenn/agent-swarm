"""Adapter for Google Gemini CLI (gemini).

Headless usage: `gemini -p "prompt" --output-format json`.
JSON schema: `response` (final answer), optional `stats`, `error`.
See https://github.com/google-gemini/gemini-cli and docs/cli/headless.md.

Notes for swarm use:
- In headless, pass --yolo when approval_mode is full-auto so tool actions (e.g. run_shell_command) are auto-approved.
- To avoid 429/capacity on preview models, set a stable model in config, e.g.:
  workers: [..., { agent: gemini, model: "gemini-2.5-flash" }]
"""

from __future__ import annotations

import asyncio
import json

from swarm.config.schema import AgentConfig, AgentType, ApprovalMode

from .base import BaseAgent, WorkerNeedsFeedback

_APPROVAL_FLAGS: dict[ApprovalMode, list[str]] = {
    # Headless docs: --yolo auto-approves all tool actions (needed for run_shell_command etc.)
    ApprovalMode.FULL_AUTO: ["--yolo"],
    ApprovalMode.AUTO_EDIT: [],
    # suggest: enable sandbox for read-only / safer execution
    ApprovalMode.SUGGEST: ["--sandbox"],
    ApprovalMode.DEFAULT: [],
}


class GeminiAgent(BaseAgent):
    """Wraps the `gemini` CLI (Google Gemini CLI).

    Lead: conversational via -p with optional session (no --continue in headless).
    Worker: one-shot `gemini -p "task" --output-format json`. With full-auto we add --yolo
    so headless auto-approves tool actions (e.g. run_shell_command).
    """

    agent_type = AgentType.GEMINI

    def _build_cmd(self) -> list[str]:
        cmd = ["gemini", "--output-format", "json"]
        cmd.extend(_APPROVAL_FLAGS.get(self.approval_mode, []))
        if self.config.model:
            cmd.extend(["-m", self.config.model])
        return cmd

    def build_execute_args(self, task: str, context: str = "") -> list[str]:
        """Gemini expects -p 'prompt' for headless."""
        prompt = f"{task}\n\n{context}" if context else task
        return [*self._build_cmd(), "-p", prompt]

    async def health_check(self) -> bool:
        try:
            await self._run_cli(["gemini", "--version"])
            return True
        except Exception:
            return False

    async def send(
        self,
        message: str,
        system_prompt: str | None = None,
        continue_session: bool = False,
    ) -> str:
        """Headless Gemini has no --continue; each call is one-shot."""
        prompt = message
        if system_prompt:
            prompt = f"{system_prompt}\n\n{message}"
        return await self.execute(prompt, context="")

    async def execute(self, task: str, context: str = "") -> str:
        prompt = f"{task}\n\n{context}" if context else task
        raw = await self._run_cli([*self._build_cmd(), "-p", prompt])
        return self._extract_result(raw)

    async def _run_cli_streaming(
        self, args: list[str], on_line=None, no_output_timeout=None
    ) -> str:
        """Buffer Gemini stdout (often pretty-printed JSON), then show only the 'response' field."""
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
            await proc.wait()
            if proc.returncode != 0:
                stderr = (await proc.stderr.read()).decode().strip()
                raise RuntimeError(f"{args[0]} exited with code {proc.returncode}: {stderr}")
            full = "\n".join(lines)
            result = self._extract_result(full)
            if on_line and result:
                for part in result.split("\n"):
                    out = on_line(part)
                    if isinstance(out, dict) and out.get("stop") and out.get("question"):
                        raise WorkerNeedsFeedback(out["question"], self.name)
            return result
        except WorkerNeedsFeedback:
            raise
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
            raise

    def _line_to_readable(self, line: str) -> str:
        """If line is Gemini JSON with response field, return it; else return line."""
        line = line.strip()
        if not line.startswith("{"):
            return line
        try:
            data = json.loads(line)
            if isinstance(data, dict):
                return data.get("response", data.get("result", line)) or line
        except json.JSONDecodeError:
            pass
        return line

    def _extract_result(self, raw: str) -> str:
        """Extract text from Gemini JSON (headless schema: response, stats, error)."""
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                return data.get("response", data.get("result", raw))
        except json.JSONDecodeError:
            pass
        return raw
