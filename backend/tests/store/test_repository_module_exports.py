def test_repository_submodules_export_public_repositories():
    from app.store.repository_modules.agents import AgentRepository
    from app.store.repository_modules.events import EventRepository
    from app.store.repository_modules.runs import RunRepository

    assert RunRepository.__name__ == "RunRepository"
    assert EventRepository.__name__ == "EventRepository"
    assert AgentRepository.__name__ == "AgentRepository"


def test_legacy_repository_module_still_reexports_classes():
    from app.store.repositories import EventRepository, RunRepository

    assert RunRepository.__name__ == "RunRepository"
    assert EventRepository.__name__ == "EventRepository"
