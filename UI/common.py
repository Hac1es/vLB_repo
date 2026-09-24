from __future__ import annotations

from contextlib import contextmanager

from nicegui import ui

from api import settings


def apply_theme():

    ui.dark_mode().enable()

    ui.add_head_html(
        """
        <style>
            html {
                font-size: 18px;
            }

            body {
                background:
                    radial-gradient(
                        circle at 20% 0%,
                        rgba(99, 102, 241, 0.10),
                        transparent 30%
                    ),
                    #09090b;
            }

            .q-card {
                border-radius: 14px;
            }

            .q-field--outlined .q-field__control {
                border-radius: 9px;
            }

            .q-uploader {
                border-radius: 10px;
                background: #0d0d12;
            }

            .q-uploader__header {
                background: transparent !important;
            }

            .q-field,
            .q-input,
            .q-select,
            .q-label,
            .q-item__label,
            .q-btn {
                font-size: 1rem;
            }

            .q-field__label {
                font-size: 1rem;
            }
        </style>
        """
    )


def section_card(
    title: str,
    description: str,
):
    card = ui.card().classes(
        "w-full bg-[#111116] border border-slate-800 shadow-none p-6"
    )

    with card:
        with ui.column().classes("gap-1 w-full"):
            ui.label(title).classes("text-lg font-semibold")

            ui.label(description).classes("text-sm text-slate-500")

        ui.separator().classes("bg-slate-800 my-5")

    return card


@contextmanager
def page_layout(
    title: str,
    subtitle: str | None = None,
    back_to: str | None = None,
):

    apply_theme()

    # ---------------------------------------------------------
    # Main container
    # ---------------------------------------------------------

    with ui.column().classes("w-full max-w-[1180px] mx-auto px-6 py-10 gap-7"):
        with ui.row().classes("w-full items-center"):
            if back_to:
                ui.button(
                    icon="arrow_back",
                    on_click=lambda: ui.navigate.to(back_to),
                ).props("flat round color=grey-5").classes("mr-2")

            with ui.column().classes("gap-0"):
                ui.label(title).classes("text-3xl font-bold tracking-tight")

                if subtitle:
                    ui.label(subtitle).classes("text-slate-400")

            ui.space()

        yield
