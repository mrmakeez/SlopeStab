from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, TimeoutError
from dataclasses import dataclass

from slope_stab.exceptions import ConvergenceError, GeometryError, ParallelExecutionError
from slope_stab.models import AnalysisResult, PrescribedCircleInput
from slope_stab.search.common import CandidateEvaluation, candidate_from_result
from slope_stab.search.surface_solver import AnalysisWorkerContext, solve_surface_for_context


@dataclass(frozen=True)
class SurfaceEvaluationTask:
    task_id: int
    surface: PrescribedCircleInput


@dataclass(frozen=True)
class SurfaceEvaluationTaskResult:
    task_id: int
    analysis_result: AnalysisResult | None
    error_reason: str | None


_WORKER_CONTEXT: AnalysisWorkerContext | None = None


def _init_surface_worker(context: AnalysisWorkerContext) -> None:
    global _WORKER_CONTEXT
    _WORKER_CONTEXT = context


def _evaluate_surface_task(task: SurfaceEvaluationTask) -> SurfaceEvaluationTaskResult:
    if _WORKER_CONTEXT is None:
        return SurfaceEvaluationTaskResult(
            task_id=task.task_id,
            analysis_result=None,
            error_reason="worker_context_uninitialized",
        )

    try:
        result = solve_surface_for_context(_WORKER_CONTEXT, task.surface)
        return SurfaceEvaluationTaskResult(task_id=task.task_id, analysis_result=result, error_reason=None)
    except (ConvergenceError, GeometryError, ValueError):
        return SurfaceEvaluationTaskResult(
            task_id=task.task_id,
            analysis_result=None,
            error_reason="evaluation_exception",
        )


class ParallelSurfaceExecutor:
    def __init__(
        self,
        context: AnalysisWorkerContext,
        workers: int,
        timeout_seconds: float | None = None,
    ) -> None:
        self._context = context
        self._timeout_seconds = timeout_seconds
        self._executor: ProcessPoolExecutor | None = ProcessPoolExecutor(
            max_workers=workers,
            initializer=_init_surface_worker,
            initargs=(context,),
        )

    def close(self) -> None:
        if self._executor is not None:
            self._executor.shutdown(wait=True, cancel_futures=True)
            self._executor = None

    def __enter__(self) -> ParallelSurfaceExecutor:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    @property
    def backend(self) -> str:
        return "process"

    def evaluate_surfaces(
        self,
        surfaces: list[PrescribedCircleInput],
        driving_moment_tol: float,
    ) -> list[CandidateEvaluation]:
        if not surfaces:
            return []
        if self._executor is None:
            raise ParallelExecutionError("Parallel executor is closed.")

        futures = [
            self._executor.submit(_evaluate_surface_task, SurfaceEvaluationTask(task_id=idx, surface=surface))
            for idx, surface in enumerate(surfaces)
        ]

        results: list[SurfaceEvaluationTaskResult] = []
        for idx, future in enumerate(futures):
            try:
                task_result = future.result(timeout=self._timeout_seconds)
            except TimeoutError as exc:
                raise ParallelExecutionError(
                    f"Parallel worker timed out while evaluating task {idx}."
                ) from exc
            except Exception as exc:
                raise ParallelExecutionError(
                    f"Parallel worker failed while evaluating task {idx}."
                ) from exc

            if not isinstance(task_result, SurfaceEvaluationTaskResult):
                raise ParallelExecutionError("Parallel worker returned invalid payload type.")
            if task_result.task_id != idx:
                raise ParallelExecutionError(
                    f"Parallel worker task id mismatch: expected {idx}, got {task_result.task_id}."
                )
            results.append(task_result)

        evaluations: list[CandidateEvaluation] = []
        for idx, task_result in enumerate(results):
            surface = surfaces[idx]
            if task_result.error_reason is not None:
                evaluations.append(
                    CandidateEvaluation(
                        surface=surface,
                        result=None,
                        valid=False,
                        reason=task_result.error_reason,
                    )
                )
                continue
            if task_result.analysis_result is None:
                raise ParallelExecutionError("Parallel worker returned no result and no error reason.")
            evaluations.append(
                candidate_from_result(
                    surface,
                    task_result.analysis_result,
                    driving_moment_tol=driving_moment_tol,
                )
            )
        return evaluations
