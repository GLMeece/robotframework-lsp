def check_data_regression(result, data_regression):
    from robocorp_ls_core import uris
    from os.path import basename

    data = {}
    for item in result:
        as_fs_path = uris.to_fs_path(item.pop("uri"))

        name = basename(as_fs_path)
        if name.endswith(".py"):
            item = "found_in_py_line_col"
        data[name] = item

    data_regression.check(data)


def test_references_basic(workspace, libspec_manager, data_regression):
    from robotframework_ls.impl.completion_context import CompletionContext
    from robotframework_ls.impl.references import references

    workspace.set_root("case_inner_keywords", libspec_manager=libspec_manager)
    doc = workspace.get_doc("case_root.robot")

    line = doc.find_line_with_contents("    Should Be Equal     ${arg1}     ${arg2}")
    col = 6
    completion_context = CompletionContext(
        doc, workspace=workspace.ws, line=line, col=col
    )
    result = references(completion_context, include_declaration=True)
    assert result

    check_data_regression(result, data_regression)
