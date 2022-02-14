def test_hover_basic(workspace, libspec_manager, data_regression):
    from robotframework_ls.impl.completion_context import CompletionContext
    from robotframework_ls.impl.hover import hover

    workspace.set_root("case4", libspec_manager=libspec_manager)
    doc = workspace.get_doc("case4.robot")
    doc = workspace.put_doc(
        "case4.robot",
        doc.source
        + """
*** Test Cases ***
Log It
    Log    """,
    )

    completion_context = CompletionContext(doc, workspace=workspace.ws)
    result = hover(completion_context)
    assert result

    contents = result["contents"]
    assert "Log" in contents["value"]
    assert contents["kind"] == "markdown"


def test_hover_basic_in_keyword_argument(workspace, libspec_manager, data_regression):
    from robotframework_ls.impl.completion_context import CompletionContext
    from robotframework_ls.impl.hover import hover

    workspace.set_root("case4", libspec_manager=libspec_manager)
    doc = workspace.get_doc("case4.robot")
    doc = workspace.put_doc(
        "case4.robot",
        doc.source
        + """
*** Test Cases ***
Log It
    Run Keyword If    ${var}    Log""",
    )

    completion_context = CompletionContext(doc, workspace=workspace.ws)
    result = hover(completion_context)
    assert result

    contents = result["contents"]
    assert "Log" in contents["value"]
    assert contents["kind"] == "markdown"


def test_hover_doc_format(workspace, libspec_manager, data_regression):
    from robotframework_ls.impl.completion_context import CompletionContext
    from robotframework_ls.impl.hover import hover

    workspace.set_root("case4", libspec_manager=libspec_manager)
    doc = workspace.put_doc(
        "case4.robot",
        """
*** Keyword ***
Some Keyword
    [Documentation]    Some *table* in docs
    ...  | =A= |  =B=  | = C =  |
    ...  | _1_ | Hello | world! |
    ...  | _2_ | Hi    |        |   
    
*** Test Case ***
Some test
    Some Keyword""",
    )

    completion_context = CompletionContext(doc, workspace=workspace.ws)
    result = hover(completion_context)
    assert result
    data_regression.check(result["contents"])
