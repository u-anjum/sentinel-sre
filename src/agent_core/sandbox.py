from e2b_code_interpreter import Sandbox

class DiagnosticSandbox:
    def __init__(self):
        self._sbx = Sandbox.create()

    @property
    def sandbox_id(self) -> str:
        return self._sbx.sandbox_id

    def run_python(self, code: str) -> dict:
        execution = self._sbx.run_code(code)
        stdout = "\n".join(execution.logs.stdout)
        stderr = "\n".join(execution.logs.stderr)
        err = f"{execution.error.name}: {execution.error.value}" if execution.error else None

        return {
            "stdout": stdout[:4000],
            "stderr": stderr[:2000],
            "error": err
        }

    def close(self) -> None:
        self._sbx.kill()