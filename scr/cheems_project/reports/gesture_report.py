"""Panel Matplotlib para visualizar resultados de actividades de gestos."""

from collections import Counter, defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt

from cheems_project.domain.models import (
    StoredHandObservation,
    StoredSession,
    StoredSessionEvent,
)


class GestureSessionReport:
    """Genera un panel descriptivo sin emitir conclusiones clínicas."""

    def generate(
        self,
        session: StoredSession,
        observations: list[StoredHandObservation],
        events: list[StoredSessionEvent],
        output_path: Path,
    ) -> Path:
        """Crea un PNG con métricas, trayectorias y marcas de una sesión."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        figure, axes = plt.subplots(2, 2, figsize=(14, 9), constrained_layout=True)
        figure.suptitle("cheems_project Perú — Reporte descriptivo de gestos", fontsize=16, fontweight="bold")

        self._draw_summary(axes[0, 0], session, observations, events)
        self._draw_gesture_counts(axes[0, 1], observations)
        self._draw_wrist_trajectory(axes[1, 0], observations)
        self._draw_timeline(axes[1, 1], observations, events)

        # Los gráficos representan observaciones técnicas, no diagnóstico clínico.
        figure.text(
            0.5,
            0.01,
            "Herramienta de apoyo: los datos requieren interpretación de un profesional.",
            ha="center",
            fontsize=9,
            color="dimgray",
        )
        figure.savefig(output_path, dpi=150, bbox_inches="tight")
        plt.close(figure)
        return output_path

    @staticmethod
    def _draw_summary(
        axis: plt.Axes,
        session: StoredSession,
        observations: list[StoredHandObservation],
        events: list[StoredSessionEvent],
    ) -> None:
        """Muestra los datos de contexto y conteos principales de la sesión, incluyendo métricas ADOS-2."""
        summary = session.summary
        stereotypies_text = ", ".join(f"{k}: {v}" for k, v in summary.get('stereotypy_counts', {}).items()) or "Ninguna"
        social_gestures_text = ", ".join(f"{k}: {v}" for k, v in summary.get('social_gesture_counts', {}).items()) or "Ninguno"
        
        text = "\n".join(
            (
                f"Sesión: {session.session_id}",
                f"Inicio: {session.started_at}",
                f"Instrucción: {session.instruction}",
                f"Frames procesados: {summary.get('frames_processed', 0)}",
                f"Frames con manos: {summary.get('frames_with_hands', 0)}",
                f"Tasa de detección: {summary.get('hand_detection_rate', 0):.1%}",
                f"Observaciones de manos guardadas: {len(observations)}",
                "-" * 40,
                f"Indicadores Clínicos (Inspirados en ADOS-2):",
                f" - Estereotipias detectadas: {summary.get('total_stereotypy_events', 0)} ({stereotypies_text})",
                f" - Gestos de relevancia social: {social_gestures_text}",
                f" - Intentos de imitación marcados: {summary.get('imitation_attempts_count', 0)}",
                f" - Intentos de imitación resueltos: {summary.get('resolved_attempts_count', 0)}",
                f" - Latencia promedio de imitación: {summary.get('average_latency_ms', 0.0)} ms",
            )
        )
        axis.axis("off")
        axis.text(0.02, 0.98, text, va="top", fontsize=10, wrap=True)

    @staticmethod
    def _draw_gesture_counts(axis: plt.Axes, observations: list[StoredHandObservation]) -> None:
        """Grafica la frecuencia de los gestos predefinidos detectados."""
        counts = Counter(observation.gesture for observation in observations)
        if not counts:
            axis.text(0.5, 0.5, "Sin gestos detectados", ha="center", va="center")
            axis.set_axis_off()
            return
        labels, values = zip(*counts.most_common())
        axis.bar(labels, values, color="#2a9d8f")
        axis.set_title("Frecuencia de gestos detectados")
        axis.set_ylabel("Observaciones")
        axis.tick_params(axis="x", rotation=25)

    @staticmethod
    def _draw_wrist_trajectory(axis: plt.Axes, observations: list[StoredHandObservation]) -> None:
        """Grafica trayectorias normalizadas de muñeca por lateralidad."""
        grouped: dict[str, list[StoredHandObservation]] = defaultdict(list)
        for observation in observations:
            grouped[observation.side].append(observation)
        if not grouped:
            axis.text(0.5, 0.5, "Sin trayectorias disponibles", ha="center", va="center")
            axis.set_axis_off()
            return
        for side, items in grouped.items():
            axis.plot(
                [item.wrist_x for item in items],
                [item.wrist_y for item in items],
                marker=".",
                markersize=3,
                label=side,
            )
        axis.set_title("Trayectoria normalizada de muñeca")
        axis.set_xlabel("X")
        axis.set_ylabel("Y")
        axis.invert_yaxis()
        axis.legend()
        axis.grid(alpha=0.3)

    @staticmethod
    def _draw_timeline(
        axis: plt.Axes,
        observations: list[StoredHandObservation],
        events: list[StoredSessionEvent],
    ) -> None:
        """Muestra detecciones de mano y marcas manuales/clínicas a lo largo del tiempo."""
        start_event = next(
            (event for event in events if event.event_type == "session_started"),
            None,
        )
        # El origen temporal es el inicio explícito de la actividad, no la vista previa.
        start_timestamp_ms = start_event.timestamp_ms if start_event else 0
        grouped: dict[str, list[StoredHandObservation]] = defaultdict(list)
        for observation in observations:
            grouped[observation.side].append(observation)
        for row, (side, items) in enumerate(grouped.items()):
            axis.scatter(
                [(item.timestamp_ms - start_timestamp_ms) / 1000 for item in items],
                [row] * len(items),
                s=8,
                label=f"Mano {side}",
            )
        for event in events:
            time_sec = (event.timestamp_ms - start_timestamp_ms) / 1000
            if event.event_type == "attempt_marked":
                axis.axvline(
                    time_sec,
                    color="#e76f51",
                    linestyle="--",
                    label="Intento marcado",
                )
            elif event.event_type.startswith("stereotypy_detected"):
                side = "Izquierda" if "Left" in event.event_type else "Derecha"
                axis.axvline(
                    time_sec,
                    color="#e63946",
                    linestyle=":",
                    linewidth=2.5,
                    label=f"Estereotipia ({side})",
                )
        axis.set_title("Línea de tiempo de observaciones")
        axis.set_xlabel("Tiempo desde el inicio (segundos)")
        axis.set_yticks(range(len(grouped)), list(grouped))
        handles, labels = axis.get_legend_handles_labels()
        unique = dict(zip(labels, handles))
        if unique:
            axis.legend(unique.values(), unique.keys(), loc="upper right")
        axis.grid(axis="x", alpha=0.3)
