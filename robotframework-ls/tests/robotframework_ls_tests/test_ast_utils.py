def test_iter_nodes():
    from robotframework_ls.impl import ast_utils
    from robotframework_ls.impl.robot_workspace import RobotDocument

    doc = RobotDocument(
        "unused", source="*** settings ***\nResource    my_resource.resource"
    )
    lst = []
    for stack, node in ast_utils.iter_all_nodes_recursive(doc.get_ast()):
        lst.append(
            "%s - %s" % ([s.__class__.__name__ for s in stack], node.__class__.__name__)
        )
    assert lst in (
        [
            "[] - SettingSection",
            "['SettingSection'] - SettingSectionHeader",
            "['SettingSection'] - ResourceImport",
        ],
        [  # version 4.0.4 onwards
            "[] - SettingSection",
            "['SettingSection'] - SectionHeader",
            "['SettingSection'] - ResourceImport",
        ],
    )


def test_print_ast(data_regression):
    from robotframework_ls.impl.robot_workspace import RobotDocument
    from robotframework_ls.impl import ast_utils

    from io import StringIO

    doc = RobotDocument("unused", source="*** settings ***")
    s = StringIO()
    ast_utils.print_ast(doc.get_ast(), stream=s)
    assert [
        x.replace("SETTING HEADER", "SETTING_HEADER") for x in s.getvalue().splitlines()
    ] in (
        [
            "  File                                               (0, 0) -> (0, 16)",
            "    SettingSection                                   (0, 0) -> (0, 16)",
            "      SettingSectionHeader                           (0, 0) -> (0, 16)",
            "      - SETTING_HEADER, '*** settings ***'                  (0, 0->16)",
            "      - EOL, ''                                            (0, 16->16)",
        ],
        [  # version 4.0.4 onwards
            "  File                                               (0, 0) -> (0, 16)",
            "    SettingSection                                   (0, 0) -> (0, 16)",
            "      SectionHeader                                  (0, 0) -> (0, 16)",
            "      - SETTING_HEADER, '*** settings ***'                  (0, 0->16)",
            "      - EOL, ''                                            (0, 16->16)",
        ],
    )


def test_find_token(workspace):
    """
    :param WorkspaceFixture workspace:
    """
    from robotframework_ls.impl import ast_utils

    workspace.set_root("case1")
    doc = workspace.get_doc("case1.robot")

    section = ast_utils.find_section(doc.get_ast(), 3)
    assert section.header.name == "Test Cases"

    token_info = ast_utils.find_token(section, 4, 1)
    assert token_info.token.type == token_info.token.TESTCASE_NAME
    assert token_info.token.value == "User can call library"

    token_info = ast_utils.find_token(section, 5, 7)
    assert token_info.token.type == token_info.token.KEYWORD
    assert token_info.token.value == "verify model"

    token_info = ast_utils.find_token(section, 50, 70)
    assert token_info is None


def test_ast_indexer():
    from robotframework_ls.impl.robot_workspace import RobotDocument
    from robotframework_ls.impl.ast_utils import _ASTIndexer

    code = """
*** Settings ***
Library           Lib1
Library           Lib2

*** Keywords ***
Keyword 1
    Sleep    1

Keyword 2
    Sleep    1
"""
    document = RobotDocument("uri", code)
    indexer = _ASTIndexer(document.get_ast())
    assert len(list(indexer.iter_indexed("Keyword"))) == 2
