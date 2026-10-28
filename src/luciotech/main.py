"""Punto de entrada de LucioTech Service Manager."""

from __future__ import annotations

import sys

from PyQt6.QtWidgets import QApplication

from luciotech.config import APP_CONFIG, APP_VERSION
from luciotech.database.connection import (
    create_db_engine,
    create_session_factory,
    resolve_database_url,
)
from luciotech.database.migrate import upgrade_database
from luciotech.services.settings_service import tax_settings
from luciotech.services.totals_service import recalculate_stored_totals
from luciotech.ui.main_window import MainWindow


def main(argv: list[str] | None = None) -> int:
    app = QApplication(sys.argv if argv is None else argv)
    app.setApplicationName(APP_CONFIG.app_name)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName(APP_CONFIG.organization_name)

    url = resolve_database_url()
    upgrade_database(url)
    engine = create_db_engine(url)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        if recalculate_stored_totals(session, tax_settings(session)):
            session.commit()
    window = MainWindow(session_factory)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
