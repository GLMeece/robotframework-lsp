import logging
import os
from pathlib import Path
import threading

import pytest

from robocorp_ls_core.protocols import ILanguageServerClient
from robocorp_ls_core.unittest_tools.cases_fixture import CasesFixture
from robotframework_ls.commands import ROBOT_INTERNAL_RFINTERACTIVE_STOP
from robotframework_ls.impl.robot_lsp_constants import (
    OPTION_ROBOT_CODE_FORMATTER_ROBOTIDY,
    OPTION_ROBOT_CODE_FORMATTER_BUILTIN_TIDY,
)


log = logging.getLogger(__name__)


def check_diagnostics(language_server, data_regression):
    from robocorp_ls_core.unittest_tools.fixtures import TIMEOUT
    from robotframework_ls_tests.fixtures import sort_diagnostics

    uri = "untitled:Untitled-1.resource"
    message_matcher = language_server.obtain_pattern_message_matcher(
        {"method": "textDocument/publishDiagnostics"}
    )
    language_server.open_doc(uri, 1)
    assert message_matcher.event.wait(TIMEOUT)

    message_matcher = language_server.obtain_pattern_message_matcher(
        {"method": "textDocument/publishDiagnostics"}
    )
    language_server.change_doc(uri, 2, "*** Invalid Invalid ***")
    assert message_matcher.event.wait(TIMEOUT)
    diag = message_matcher.msg["params"]["diagnostics"]
    data_regression.check(sort_diagnostics(diag), basename="diagnostics")


def test_diagnostics(language_server, ws_root_path, data_regression):
    language_server.initialize(ws_root_path, process_id=os.getpid())
    import robot

    env = {
        "PYTHONPATH": os.path.dirname(os.path.dirname(os.path.abspath(robot.__file__)))
    }
    language_server.settings(
        {"settings": {"robot.python.env": env, "robot.lint.robocop.enabled": True}}
    )
    check_diagnostics(language_server, data_regression)


def test_diagnostics_robocop(language_server, ws_root_path, data_regression):
    from robotframework_ls_tests.fixtures import sort_diagnostics
    from robocorp_ls_core.unittest_tools.fixtures import TIMEOUT

    language_server.initialize(ws_root_path, process_id=os.getpid())

    language_server.settings({"settings": {"robot.lint.robocop.enabled": True}})

    uri = "untitled:Untitled-1"
    message_matcher = language_server.obtain_pattern_message_matcher(
        {"method": "textDocument/publishDiagnostics"}
    )
    language_server.open_doc(uri, 1)
    assert message_matcher.event.wait(TIMEOUT)

    message_matcher = language_server.obtain_pattern_message_matcher(
        {"method": "textDocument/publishDiagnostics"}
    )
    language_server.change_doc(
        uri,
        2,
        """
*** Test Cases ***
Test
    Fail
    
Test
    Fail
""",
    )
    assert message_matcher.event.wait(TIMEOUT)
    diag = message_matcher.msg["params"]["diagnostics"]
    data_regression.check(sort_diagnostics(diag), basename="test_diagnostics_robocop")


def test_diagnostics_robocop_configuration_file(
    language_server, ws_root_path, data_regression
):
    from robotframework_ls_tests.fixtures import sort_diagnostics
    from robocorp_ls_core.unittest_tools.fixtures import TIMEOUT
    from robocorp_ls_core import uris

    language_server.initialize(ws_root_path, process_id=os.getpid())
    language_server.settings({"settings": {"robot.lint.robocop.enabled": True}})
    src = os.path.join(ws_root_path, "my", "src")
    os.makedirs(src)
    target_robot = os.path.join(src, "target.robot")
    config_file = os.path.join(ws_root_path, "my", ".robocop")
    with open(config_file, "w") as stream:
        stream.write(
            """
--exclude missing-doc-test-case
--include missing-doc-suite
"""
        )

    uri = uris.from_fs_path(target_robot)
    message_matcher = language_server.obtain_pattern_message_matcher(
        {"method": "textDocument/publishDiagnostics"}
    )
    language_server.open_doc(
        uri,
        1,
        text="""
*** Test Cases ***
Test
    Fail

""",
    )
    assert message_matcher.event.wait(TIMEOUT)
    diag = message_matcher.msg["params"]["diagnostics"]
    data_regression.check(
        sort_diagnostics(diag), basename="test_diagnostics_robocop_configuration_file"
    )


def test_section_completions_integrated(language_server, ws_root_path, data_regression):
    language_server.initialize(ws_root_path, process_id=os.getpid())
    uri = "untitled:Untitled-1"
    language_server.open_doc(uri, 1)
    language_server.change_doc(uri, 2, "*settin")

    def check(expected):
        completions = language_server.get_completions(uri, 0, 7)
        del completions["id"]
        data_regression.check(completions, expected)

    check("completion_settings_plural")

    language_server.settings(
        {
            "settings": {
                "robot": {"completions": {"section_headers": {"form": "singular"}}}
            }
        }
    )
    check("completion_settings_singular")

    language_server.settings(
        {"settings": {"robot": {"completions": {"section_headers": {"form": "both"}}}}}
    )
    check("completion_settings_both")

    language_server.settings(
        {
            "settings": {
                "robot": {"completions": {"section_headers": {"form": "plural"}}}
            }
        }
    )
    check("completion_settings_plural")


def test_keyword_completions_integrated_pythonpath_resource(
    language_server_tcp, ws_root_path, data_regression, cases
):
    from robocorp_ls_core.workspace import Document

    case4_path = cases.get_path("case4")

    language_server = language_server_tcp
    language_server.initialize(ws_root_path, process_id=os.getpid())
    uri = "untitled:Untitled-1"
    language_server.open_doc(uri, 1)
    contents = """
*** Settings ***
Resource    case4resource.txt

*** Test Cases ***
Check It
    Yet Another Equ"""
    language_server.change_doc(uri, 2, contents)

    language_server_tcp.settings({"settings": {"robot": {"pythonpath": [case4_path]}}})

    def request_completion():
        doc = Document("", source=contents)
        line, col = doc.get_last_line_col()
        completions = language_server.get_completions(uri, line, col)
        del completions["id"]
        return completions

    data_regression.check(request_completion())

    # Removing should no longer find it.
    language_server_tcp.settings({"settings": {"robot": {"pythonpath": []}}})

    data_regression.check(request_completion(), basename="no_entries")


def test_keyword_completions_integrated_pythonpath_library(
    language_server_tcp: ILanguageServerClient, ws_root_path, data_regression, cases
):
    from robocorp_ls_core.workspace import Document

    case1_path = cases.get_path("case1")

    language_server = language_server_tcp
    language_server.initialize(ws_root_path, process_id=os.getpid())
    uri = "untitled:Untitled-1"
    language_server.open_doc(uri, 1)
    contents = """
*** Settings ***
Library    case1_library

*** Test Cases ***
Check It
    Verify Mod"""
    language_server.change_doc(uri, 2, contents)

    language_server_tcp.settings({"settings": {"robot": {"pythonpath": [case1_path]}}})

    def request_completion():
        doc = Document("", source=contents)
        line, col = doc.get_last_line_col()
        completions = language_server.get_completions(uri, line, col)
        del completions["id"]
        return completions

    data_regression.check(request_completion())

    # Note: for libraries, if we found it, we keep it in memory (so, even though
    # we removed the entry, it'll still be accessible).
    language_server_tcp.settings({"settings": {"robot": {"pythonpath": []}}})

    data_regression.check(request_completion())


def test_completions_after_library(
    language_server_tcp: ILanguageServerClient, ws_root_path, data_regression, cases
):
    from robocorp_ls_core.workspace import Document

    case1_path = cases.get_path("case1")

    language_server = language_server_tcp
    language_server.initialize(ws_root_path, process_id=os.getpid())
    uri = "untitled:Untitled-1"
    language_server.open_doc(uri, 1)
    contents = """
*** Settings ***
Library    """
    language_server.change_doc(uri, 2, contents)

    language_server_tcp.settings({"settings": {"robot": {"pythonpath": [case1_path]}}})

    def request_completion():
        doc = Document("", source=contents)
        line, col = doc.get_last_line_col()
        completions = language_server.get_completions(uri, line, col)
        del completions["id"]
        return completions

    assert not request_completion()["result"]


def test_keyword_completions_prefer_local_library_import(
    language_server_tcp: ILanguageServerClient, ws_root_path, data_regression, cases
):
    from robocorp_ls_core.workspace import Document
    from robocorp_ls_core import uris

    try:
        os.makedirs(ws_root_path)
    except:
        pass

    language_server = language_server_tcp
    language_server.initialize(ws_root_path, process_id=os.getpid())
    case1_robot_path = cases.get_path("case1/case1.robot")
    contents = """
*** Settings ***
Library           case1_library

*** Test Cases ***
User can call library
    verify model   1
    verify_another_mod"""

    uri = uris.from_fs_path(case1_robot_path)
    language_server.open_doc(uri, 1, text=contents)

    def request_completion():
        doc = Document("", source=contents)
        line, col = doc.get_last_line_col()
        completions = language_server.get_completions(uri, line, col)
        del completions["id"]
        return completions

    data_regression.check(request_completion())


def test_variables_completions_integrated(
    language_server_tcp: ILanguageServerClient, ws_root_path, data_regression
):
    from robocorp_ls_core.workspace import Document

    language_server = language_server_tcp
    language_server.initialize(ws_root_path, process_id=os.getpid())
    uri = "untitled:Untitled-1"
    language_server.open_doc(uri, 1)
    contents = """
*** Variables ***
${NAME}         Robot Framework
${VERSION}      2.0
${ROBOT}        ${NAME} ${VERSION}

*** Test Cases ***
List Variable
    Log    ${NAME}
    Should Contain    ${"""
    language_server.change_doc(uri, 2, contents)

    doc = Document("", source=contents)
    line, col = doc.get_last_line_col()
    completions = language_server.get_completions(uri, line, col)
    del completions["id"]
    data_regression.check(completions, "variable_completions")

    # Note: for libraries, if we found it, we keep it in memory (so, even though
    # we removed the entry, it'll still be accessible).
    language_server_tcp.settings({"settings": {"robot": {"variables": {"myvar1": 10}}}})

    completions = language_server.get_completions(uri, line, col)
    labels = [x["label"] for x in completions["result"]]
    assert "${myvar1}" in labels


def test_variables_resolved_on_completion_integrated(
    language_server_tcp: ILanguageServerClient, workspace_dir, data_regression, cases
):
    from robocorp_ls_core.workspace import Document

    language_server = language_server_tcp
    language_server.initialize(workspace_dir, process_id=os.getpid())
    uri = "untitled:Untitled-1"
    language_server.open_doc(uri, 1)
    contents = """*** Settings ***
Library           ${ROOT}/directory/my_library.py


*** Keywords ***
Some Keyword
    In Lib"""
    language_server.change_doc(uri, 2, contents)

    # Note: for libraries, if we found it, we keep it in memory (so, even though
    # we removed the entry, it'll still be accessible).
    language_server_tcp.settings(
        {
            "settings": {
                "robot": {"variables": {"ROOT": cases.get_path("case_same_basename")}}
            }
        }
    )

    doc = Document("", source=contents)
    line, col = doc.get_last_line_col()
    completions = language_server.get_completions(uri, line, col)
    data_regression.check(completions)


def test_env_variables_resolved_on_completion_integrated(
    language_server_tcp: ILanguageServerClient, workspace_dir, data_regression, cases
):
    from robocorp_ls_core.workspace import Document

    language_server = language_server_tcp
    language_server.initialize(workspace_dir, process_id=os.getpid())
    uri = "untitled:Untitled-1"
    language_server.open_doc(uri, 1)
    contents = """*** Settings ***
Library           %{ROOT}/directory/my_library.py


*** Keywords ***
Some Keyword
    In Lib"""
    language_server.change_doc(uri, 2, contents)

    # Note: for libraries, if we found it, we keep it in memory (so, even though
    # we removed the entry, it'll still be accessible).
    language_server_tcp.settings(
        {
            "settings": {
                "robot": {
                    "python": {"env": {"ROOT": cases.get_path("case_same_basename")}}
                }
            }
        }
    )

    doc = Document("", source=contents)
    line, col = doc.get_last_line_col()
    completions = language_server.get_completions(uri, line, col)
    data_regression.check(completions)

    contents = """*** Settings ***
Library           %{ROOT}/directory/my_library.py


*** Keywords ***
Some Keyword
    In Lib 2"""
    language_server.change_doc(uri, 2, contents)
    definitions = language_server.find_definitions(uri, line, col)
    found = definitions["result"]
    assert len(found) == 1
    assert found[0]["uri"].endswith("my_library.py")


def test_snippets_completions_integrated(
    language_server_tcp, ws_root_path, data_regression
):
    from robocorp_ls_core.workspace import Document

    language_server = language_server_tcp
    language_server.initialize(ws_root_path, process_id=os.getpid())
    uri = "untitled:Untitled-1"
    language_server.open_doc(uri, 1)
    contents = """
*** Test Cases ***
List Variable
    for in"""
    language_server.change_doc(uri, 2, contents)

    doc = Document("", source=contents)
    line, col = doc.get_last_line_col()
    completions = language_server.get_completions(uri, line, col)
    del completions["id"]
    data_regression.check(completions, "snippet_completions")


def test_restart_when_api_dies(language_server_tcp, ws_root_path, data_regression):
    from robocorp_ls_core.basic import kill_process_and_subprocesses
    from robocorp_ls_core import basic
    from robotframework_ls.server_manager import _ServerApi
    import time

    # Check just with language_server_tcp as it's easier to kill the subprocess.

    server_apis = set()
    server_processes = set()

    def on_get_robotframework_api_client(server_api):
        if (
            server_api.robot_framework_language_server
            is language_server_tcp.language_server_instance
        ):
            server_apis.add(server_api)
            server_processes.add(server_api._server_process.pid)

    with basic.after(
        _ServerApi, "get_robotframework_api_client", on_get_robotframework_api_client
    ):
        language_server_tcp.initialize(ws_root_path, process_id=os.getpid())
        import robot

        env = {
            "PYTHONPATH": os.path.dirname(
                os.path.dirname(os.path.abspath(robot.__file__))
            )
        }
        language_server_tcp.settings(
            {"settings": {"robot.python.env": env, "robot.lint.robocop.enabled": True}}
        )

        processes_per_api = 3

        check_diagnostics(language_server_tcp, data_regression)
        assert len(server_apis) == processes_per_api
        assert len(server_processes) == processes_per_api

        check_diagnostics(language_server_tcp, data_regression)
        assert len(server_apis) == processes_per_api
        assert len(server_processes) == processes_per_api

        log.info("Killing server api process.")
        for pid in server_processes:
            kill_process_and_subprocesses(pid)

        # Just make sure the connection is properly dropped before re-requesting.
        time.sleep(0.2)

        check_diagnostics(language_server_tcp, data_regression)
        assert len(server_processes) == processes_per_api * 2
        assert len(server_apis) == processes_per_api


def test_missing_message(language_server, ws_root_path):
    language_server.initialize(ws_root_path)

    # Just ignore this one (it's not a request because it has no id).
    language_server.write(
        {
            "jsonrpc": "2.0",
            "method": "invalidMessageSent",
            "params": {"textDocument": {"uri": "untitled:Untitled-1", "version": 2}},
        }
    )

    # Make sure that we have a response if it's a request (i.e.: it has an id).
    msg = language_server.request(
        {
            "jsonrpc": "2.0",
            "id": "22",
            "method": "invalidMessageSent",
            "params": {"textDocument": {"uri": "untitled:Untitled-1", "version": 2}},
        }
    )

    assert msg["error"]["code"] == -32601


def test_exit_with_parent_process_died(
    language_server_process, language_server_io, ws_root_path
):
    """
    :note: Only check with the language_server_io (because that's in another process).
    """
    from robocorp_ls_core.subprocess_wrapper import subprocess
    import sys
    from robocorp_ls_core.basic import is_process_alive
    from robocorp_ls_core.basic import kill_process_and_subprocesses
    from robocorp_ls_core.unittest_tools.fixtures import wait_for_test_condition

    language_server = language_server_io
    dummy_process = subprocess.Popen(
        [sys.executable, "-c", "import time;time.sleep(10000)"]
    )

    language_server.initialize(ws_root_path, process_id=dummy_process.pid)

    assert is_process_alive(dummy_process.pid)
    assert is_process_alive(language_server_process.pid)

    kill_process_and_subprocesses(dummy_process.pid)

    wait_for_test_condition(lambda: not is_process_alive(dummy_process.pid))
    wait_for_test_condition(lambda: not is_process_alive(language_server_process.pid))
    language_server_io.require_exit_messages = False


@pytest.mark.parametrize(
    "formatter",
    [OPTION_ROBOT_CODE_FORMATTER_ROBOTIDY, OPTION_ROBOT_CODE_FORMATTER_BUILTIN_TIDY],
)
def test_code_format_integrated(
    language_server, ws_root_path, data_regression, formatter
):
    language_server.initialize(ws_root_path, process_id=os.getpid())
    uri = "untitled:Untitled-1"
    language_server.open_doc(uri, 1)
    language_server.settings({"settings": {"robot.codeFormatter": formatter}})
    language_server.change_doc(uri, 2, "***settings***\nDocumentation  Some doc")
    ret = language_server.request_source_format(uri)

    from robot import get_version

    version = get_version(naked=True).split(".")[0]
    if version == "5":
        version = "4"

    basename = "test_code_format_integrated_text_edits_" + formatter
    if formatter == OPTION_ROBOT_CODE_FORMATTER_ROBOTIDY:
        basename += "_" + version
    data_regression.check(
        ret,
        basename=basename,
    )

    language_server.change_doc(uri, 3, "[Documentation]\n")
    ret = language_server.request_source_format(uri)
    assert ret["result"] == []


def test_find_definition_integrated_library(
    language_server: ILanguageServerClient, cases, workspace_dir
):
    from robocorp_ls_core import uris

    cases.copy_to("case1", workspace_dir)

    language_server.initialize(workspace_dir, process_id=os.getpid())
    case1_robot = os.path.join(workspace_dir, "case1.robot")
    assert os.path.exists(case1_robot)
    uri = uris.from_fs_path(case1_robot)

    language_server.open_doc(uri, 1, text=None)
    ret = language_server.find_definitions(uri, 5, 6)
    result = ret["result"]
    assert len(result) == 1
    check = next(iter(result))
    assert check["uri"].endswith("case1_library.py")
    assert check["range"] == {
        "start": {"line": 7, "character": 0},
        "end": {"line": 7, "character": 0},
    }


def test_find_definition_keywords(
    language_server: ILanguageServerClient, cases, workspace_dir
):
    from robocorp_ls_core import uris

    cases.copy_to("case2", workspace_dir)

    language_server.initialize(workspace_dir, process_id=os.getpid())
    case2_robot = os.path.join(workspace_dir, "case2.robot")
    assert os.path.exists(case2_robot)
    uri = uris.from_fs_path(case2_robot)

    language_server.open_doc(uri, 1, text=None)
    ret = language_server.find_definitions(uri, 7, 6)
    result = ret["result"]
    assert len(result) == 1
    check = next(iter(result))
    assert check["uri"].endswith("case2.robot")
    assert check["range"] == {
        "start": {"line": 1, "character": 0},
        "end": {"line": 4, "character": 5},
    }


def test_signature_help_integrated(
    language_server_io: ILanguageServerClient, ws_root_path, data_regression
):
    from robocorp_ls_core.workspace import Document

    language_server = language_server_io

    language_server.initialize(ws_root_path, process_id=os.getpid())
    uri = "untitled:Untitled-1"
    txt = """
*** Test Cases ***
Log It
    Log    """
    doc = Document("", txt)
    language_server.open_doc(uri, 1, txt)
    line, col = doc.get_last_line_col()

    ret = language_server.request_signature_help(uri, line, col)
    result = ret["result"]
    signatures = result["signatures"]

    # Don't check the signature documentation in the data regression so that the
    # test doesn't become brittle.
    docs = signatures[0].pop("documentation")
    assert "Log" in docs

    data_regression.check(result)


def test_hover_integrated(
    language_server_io: ILanguageServerClient, ws_root_path, data_regression
):
    from robocorp_ls_core.workspace import Document
    from robocorp_ls_core.lsp import HoverTypedDict

    language_server = language_server_io

    language_server.initialize(ws_root_path, process_id=os.getpid())
    uri = "untitled:Untitled-1"
    txt = """
*** Test Cases ***
Log It
    Log    """
    doc = Document("", txt)
    language_server.open_doc(uri, 1, txt)
    line, col = doc.get_last_line_col()

    ret = language_server.request_hover(uri, line, col)
    result: HoverTypedDict = ret["result"]

    contents = result["contents"]
    assert "Log" in contents["value"]
    assert contents["kind"] == "markdown"


def test_workspace_symbols_integrated(
    language_server_io: ILanguageServerClient, ws_root_path, data_regression
):
    language_server = language_server_io

    language_server.initialize(ws_root_path, process_id=os.getpid())

    ret = language_server.request_workspace_symbols()
    result = ret["result"]
    assert len(result) > 0


def test_folding_range_integrated(
    language_server_io: ILanguageServerClient, ws_root_path, data_regression
):
    language_server = language_server_io

    language_server.initialize(ws_root_path, process_id=os.getpid())
    uri = "untitled:Untitled-1"
    txt = """
*** Test Cases ***
Log It
    Log    

Log It2
    Log    

"""
    language_server.open_doc(uri, 1, txt)

    ret = language_server.request_folding_range(uri)
    result = ret["result"]
    data_regression.check(result)


def test_code_lens_integrated(
    language_server_io: ILanguageServerClient, ws_root_path, data_regression
):
    from robocorp_ls_core import uris
    from robotframework_ls_tests.fixtures import check_code_lens_data_regression

    language_server = language_server_io

    language_server.initialize(ws_root_path, process_id=os.getpid())
    os.makedirs(ws_root_path, exist_ok=True)
    uri = uris.from_fs_path(os.path.join(ws_root_path, "my.robot"))

    txt = """
*** Test Case ***
Log It
    Log    

*** Task ***
Log It2
    Log    

"""
    language_server.open_doc(uri, 1, txt)

    ret = language_server.request_code_lens(uri)
    found = ret["result"]
    check_code_lens_data_regression(data_regression, found)


def test_code_lens_integrated_suites(
    language_server_io: ILanguageServerClient, ws_root_path, data_regression
):
    from robocorp_ls_core import uris
    from robotframework_ls_tests.fixtures import check_code_lens_data_regression

    language_server = language_server_io

    language_server.initialize(ws_root_path, process_id=os.getpid())
    os.makedirs(ws_root_path, exist_ok=True)
    uri = uris.from_fs_path(os.path.join(ws_root_path, "my.robot"))
    txt = """
*** Task ***
Log It
    Log    

Log It2
    Log    

"""
    language_server.open_doc(uri, 1, txt)

    ret = language_server.request_code_lens(uri)
    found = ret["result"]
    check_code_lens_data_regression(data_regression, found)


def test_list_tests_integrated(
    language_server_io: ILanguageServerClient, ws_root_path, data_regression
):
    language_server = language_server_io

    language_server.initialize(ws_root_path, process_id=os.getpid())
    uri = "untitled:Untitled-1"
    txt = """
*** Test Case ***
Log It
    Log    

*** Task ***
Log It2
    Log    

"""
    language_server.open_doc(uri, 1, txt)

    ret = language_server.execute_command("robot.listTests", [{"uri": uri}])
    found = ret["result"]
    data_regression.check(found)


def test_document_symbol_integrated(
    language_server_io: ILanguageServerClient, ws_root_path, data_regression
):
    language_server = language_server_io

    language_server.initialize(ws_root_path, process_id=os.getpid())
    uri = "untitled:Untitled-1"
    txt = """
*** Task ***
Log It
    Log    

Log It2
    Log    

"""
    language_server.open_doc(uri, 1, txt)

    ret = language_server.request_document_symbol(uri)
    found = ret["result"]
    data_regression.check(found)


def test_shadowing_libraries(language_server_io: ILanguageServerClient, workspace_dir):
    from robocorp_ls_core import uris
    from pathlib import Path
    from robocorp_ls_core.unittest_tools.fixtures import TIMEOUT

    language_server = language_server_io

    os.makedirs(workspace_dir, exist_ok=True)
    builtin_lib = Path(workspace_dir) / "builtin.py"
    case1_lib = Path(workspace_dir) / "case1.robot"
    case2_lib = Path(workspace_dir) / "case2.robot"

    builtin_lib.write_text(
        """
def something():
    pass
"""
    )

    case1_lib.write_text(
        """
*** Settings ***
Library           builtin

*** Test Cases ***
User can call builtin
    Something
"""
    )

    case2_lib.write_text(
        """
*** Test Cases ***
User can call builtin 2
    Log  Task executed
"""
    )

    language_server.initialize(workspace_dir, process_id=os.getpid())

    uri1 = uris.from_fs_path(str(case1_lib))
    uri2 = uris.from_fs_path(str(case2_lib))

    for _i in range(2):
        message_matcher = language_server.obtain_pattern_message_matcher(
            {"method": "textDocument/publishDiagnostics"}
        )

        language_server.open_doc(uri1, 1, text=None)
        assert message_matcher.event.wait(TIMEOUT)
        assert message_matcher.msg["params"]["uri"] == uri1
        assert message_matcher.msg["params"]["diagnostics"] == []

        message_matcher = language_server.obtain_pattern_message_matcher(
            {"method": "textDocument/publishDiagnostics"}
        )

        language_server.open_doc(uri2, 1, text=None)
        assert message_matcher.event.wait(TIMEOUT)
        assert message_matcher.msg["params"]["uri"] == uri2
        assert message_matcher.msg["params"]["diagnostics"] == []

        language_server.close_doc(uri2)
        language_server.close_doc(uri1)


class _RfInterpreterInfo:
    def __init__(self, interpreter_id: int, uri: str):
        self.interpreter_id = interpreter_id
        self.uri = uri


@pytest.fixture
def rf_interpreter_startup(language_server_io: ILanguageServerClient, ws_root_path):
    from robotframework_ls.commands import ROBOT_INTERNAL_RFINTERACTIVE_START
    from robotframework_ls.commands import ROBOT_INTERNAL_RFINTERACTIVE_STOP
    from robocorp_ls_core import uris

    language_server = language_server_io

    language_server.initialize(ws_root_path, process_id=os.getpid())
    os.makedirs(ws_root_path, exist_ok=True)
    uri = uris.from_fs_path(os.path.join(ws_root_path, "my.robot"))

    ret1 = language_server.execute_command(
        ROBOT_INTERNAL_RFINTERACTIVE_START, [{"uri": uri}]
    )
    assert ret1["result"] == {
        "success": True,
        "message": None,
        "result": {"interpreter_id": 0},
    }
    yield _RfInterpreterInfo(interpreter_id=0, uri=uri)
    # Note: success could be False if it was stopped in the test...
    language_server.execute_command(
        ROBOT_INTERNAL_RFINTERACTIVE_STOP, [{"interpreter_id": 0}]
    )


def test_rf_interactive_integrated_basic(
    language_server_io: ILanguageServerClient,
    rf_interpreter_startup: _RfInterpreterInfo,
):
    from robotframework_ls.commands import ROBOT_INTERNAL_RFINTERACTIVE_START
    from robotframework_ls.commands import ROBOT_INTERNAL_RFINTERACTIVE_STOP
    from robotframework_ls.commands import ROBOT_INTERNAL_RFINTERACTIVE_EVALUATE
    from robotframework_ls.commands import ROBOT_INTERNAL_RFINTERACTIVE_SEMANTIC_TOKENS
    from robotframework_ls.commands import ROBOT_INTERNAL_RFINTERACTIVE_COMPLETIONS
    from robocorp_ls_core.lsp import Position

    language_server = language_server_io
    uri = rf_interpreter_startup.uri

    ret2 = language_server.execute_command(
        ROBOT_INTERNAL_RFINTERACTIVE_START, [{"uri": uri}]
    )
    assert ret2["result"] == {
        "success": True,
        "message": None,
        "result": {"interpreter_id": 1},
    }

    stop1 = language_server.execute_command(
        ROBOT_INTERNAL_RFINTERACTIVE_STOP, [{"interpreter_id": 0}]
    )
    assert stop1["result"] == {"success": True, "message": None, "result": None}

    stop_inexistant = language_server.execute_command(
        ROBOT_INTERNAL_RFINTERACTIVE_STOP, [{"interpreter_id": 22}]
    )
    assert stop_inexistant["result"] == {
        "success": False,
        "message": "Did not find interpreter with id: 22",
        "result": None,
    }

    message_matcher = language_server.obtain_pattern_message_matcher(
        {"method": "interpreter/output"}
    )
    eval2 = language_server.execute_command(
        ROBOT_INTERNAL_RFINTERACTIVE_EVALUATE,
        [
            {
                "interpreter_id": 1,
                "code": """
*** Task ***
Some task
    Log    Something     console=True
""",
            }
        ],
    )
    assert eval2["result"] == {"success": True, "message": None, "result": None}
    assert message_matcher.event.wait(10)
    assert message_matcher.msg == {
        "jsonrpc": "2.0",
        "method": "interpreter/output",
        "params": {"output": "Something\n", "category": "stdout", "interpreter_id": 1},
    }

    semantic_tokens = language_server.execute_command(
        ROBOT_INTERNAL_RFINTERACTIVE_SEMANTIC_TOKENS,
        [{"interpreter_id": 1, "code": "Log    Something     console=True"}],
    )

    data = semantic_tokens["result"]["data"]
    assert data == [
        0,
        0,
        3,
        7,
        0,
        0,
        7,
        9,
        12,
        0,
        0,
        14,
        7,
        11,
        0,
        0,
        7,
        1,
        6,
        0,
        0,
        1,
        4,
        12,
        0,
    ]

    completions = language_server.execute_command(
        ROBOT_INTERNAL_RFINTERACTIVE_COMPLETIONS,
        [{"interpreter_id": 1, "code": "Lo", "position": Position(0, 2).to_dict()}],
    )

    for completion in completions["result"]["suggestions"]:
        if completion["label"] == "Log (BuiltIn)":
            break
    else:
        raise AssertionError('Did not find "Log" in the suggestions.')

    stop2 = language_server.execute_command(
        ROBOT_INTERNAL_RFINTERACTIVE_STOP, [{"interpreter_id": 1}]
    )
    assert stop2["result"] == {"success": True, "message": None, "result": None}


def test_rf_interactive_integrated_input_request(
    language_server_io: ILanguageServerClient,
    rf_interpreter_startup: _RfInterpreterInfo,
):
    from robotframework_ls.commands import ROBOT_INTERNAL_RFINTERACTIVE_EVALUATE
    from robocorp_ls_core import uris

    language_server = language_server_io
    uri = rf_interpreter_startup.uri
    robot_file = uris.to_fs_path(uri)
    lib_file = os.path.join(os.path.dirname(robot_file), "my_lib.py")
    with open(lib_file, "w", encoding="utf-8") as stream:
        stream.write(
            r"""
def check_input():
    import sys
    sys.__stdout__.write('Enter something\n')
    return input()
"""
        )

    message_matcher = language_server.obtain_pattern_message_matcher(
        {"method": "interpreter/output"}
    )
    language_server.execute_command(
        ROBOT_INTERNAL_RFINTERACTIVE_EVALUATE,
        [{"interpreter_id": 0, "code": "*** Settings ***\nLibrary    ./my_lib.py"}],
    )

    def run_in_thread():
        language_server.execute_command(
            ROBOT_INTERNAL_RFINTERACTIVE_EVALUATE,
            [
                {
                    "interpreter_id": 0,
                    "code": """
*** Test Case ***
Test
    ${var}=  Check Input
    Log    ${var}     console=True
""",
                }
            ],
        )

    t = threading.Thread(target=run_in_thread)
    t.start()

    assert message_matcher.event.wait(10)
    assert message_matcher.msg == {
        "jsonrpc": "2.0",
        "method": "interpreter/output",
        "params": {
            "output": "Enter something\n",
            "category": "stdout",
            "interpreter_id": 0,
        },
    }
    import time

    time.sleep(0.5)

    message_matcher = language_server.obtain_pattern_message_matcher(
        {"method": "interpreter/output"}
    )

    language_server.execute_command(
        ROBOT_INTERNAL_RFINTERACTIVE_EVALUATE,
        [{"interpreter_id": 0, "code": "EnterThis"}],
    )
    assert message_matcher.event.wait(10)
    assert message_matcher.msg == {
        "jsonrpc": "2.0",
        "method": "interpreter/output",
        "params": {"output": "EnterThis\n", "category": "stdout", "interpreter_id": 0},
    }

    t.join(10)
    assert not t.is_alive()


def test_rf_interactive_integrated_hook_robocorp_update_env(
    language_server_io: ILanguageServerClient, cases: CasesFixture, workspace_dir: str
):
    from robotframework_ls.commands import ROBOT_INTERNAL_RFINTERACTIVE_EVALUATE
    from robocorp_ls_core import uris
    from robotframework_ls.commands import ROBOT_INTERNAL_RFINTERACTIVE_START

    language_server = language_server_io

    cases.copy_to("custom_env", workspace_dir)

    p = Path(workspace_dir)
    plugins_path = p / "plugins"
    assert plugins_path.exists()
    language_server.initialize(
        workspace_dir,
        process_id=os.getpid(),
        initialization_options={"pluginsDir": str(plugins_path)},
    )

    p = Path(workspace_dir) / "env1" / "caselib1.robot"
    assert p.exists()

    uri = uris.from_fs_path(str(p))

    handled_update_launch_env = threading.Event()

    def handle_execute_workspace_command(method, message_id, params):
        assert method == "$/executeWorkspaceCommand"
        assert isinstance(params, dict)

        command = params["command"]
        assert command == "robocorp.updateLaunchEnv"

        arguments = params["arguments"]
        assert arguments["targetRobot"]
        env = arguments["env"]
        env["CUSTOM_VAR_SET_FROM_TEST"] = "EXPECTED VALUE"

        contents = {"jsonrpc": "2.0", "id": message_id, "result": env}
        language_server.write(contents)
        handled_update_launch_env.set()
        return True

    language_server.register_request_handler(
        "$/executeWorkspaceCommand", handle_execute_workspace_command
    )

    ret1 = language_server.execute_command(
        ROBOT_INTERNAL_RFINTERACTIVE_START, [{"uri": uri}]
    )
    assert handled_update_launch_env.wait(5)
    try:
        assert ret1["result"] == {
            "success": True,
            "message": None,
            "result": {"interpreter_id": 0},
        }

        message_matcher_interpreter_output = (
            language_server.obtain_pattern_message_matcher(
                {"method": "interpreter/output"}
            )
        )

        def run_in_thread():
            language_server.execute_command(
                ROBOT_INTERNAL_RFINTERACTIVE_EVALUATE,
                [
                    {
                        "interpreter_id": 0,
                        "code": """
*** Test Case ***
Test
    Log to console   %{CUSTOM_VAR_SET_FROM_TEST}
""",
                    }
                ],
            )

        t = threading.Thread(target=run_in_thread)
        t.start()

        assert message_matcher_interpreter_output.event.wait(10)
        assert message_matcher_interpreter_output.msg == {
            "jsonrpc": "2.0",
            "method": "interpreter/output",
            "params": {
                "output": "EXPECTED VALUE\n",
                "category": "stdout",
                "interpreter_id": 0,
            },
        }

    finally:
        # Note: success could be False if it was stopped in the test...
        language_server.execute_command(
            ROBOT_INTERNAL_RFINTERACTIVE_STOP, [{"interpreter_id": 0}]
        )


def test_rf_interactive_integrated_completions(
    language_server_io: ILanguageServerClient,
    rf_interpreter_startup: _RfInterpreterInfo,
):

    from robotframework_ls.commands import ROBOT_INTERNAL_RFINTERACTIVE_COMPLETIONS
    from robocorp_ls_core.lsp import Position

    language_server = language_server_io
    completions = language_server.execute_command(
        ROBOT_INTERNAL_RFINTERACTIVE_COMPLETIONS,
        [
            {
                "interpreter_id": rf_interpreter_startup.interpreter_id,
                "code": "\n\nLo",
                "position": Position(2, 2).to_dict(),
            }
        ],
    )

    for completion in completions["result"]["suggestions"]:
        if completion["label"] == "Log (BuiltIn)":
            assert completion == {
                "label": "Log (BuiltIn)",
                "kind": 0,
                "insertText": "Log    ${1:message}",
                "insertTextRules": 4,
                "documentation": "Log(message, level=INFO, html=False, console=False, repr=False, formatter=str)\n\nLogs the given message with the given level.\n\n Valid levels are TRACE, DEBUG, INFO (default), HTML, WARN, and ERROR. Messages below the current active log level are ignored. See [Set Log Level](#Set%20Log%20Level) keyword and --loglevel command line option for more details about setting the level.\n\n Messages logged with the WARN or ERROR levels will be automatically visible also in the console and in the Test Execution Errors section in the log file.\n\n If the html argument is given a true value (see [Boolean arguments](#Boolean%20arguments)), the message will be considered HTML and special characters such as < are not escaped. For example, logging <img src=\"image.png\"> creates an image when html is true, but otherwise the message is that exact string. An alternative to using the html argument is using the HTML pseudo log level. It logs the message as HTML using the INFO level.\n\n If the console argument is true, the message will be written to the console where test execution was started from in addition to the log file. This keyword always uses the standard output stream and adds a newline after the written message. Use [Log To Console](#Log%20To%20Console) instead if either of these is undesirable,\n\n The formatter argument controls how to format the string representation of the message. Possible values are str (default), repr and ascii, and they work similarly to Python built-in functions with same names. When using repr, bigger lists, dictionaries and other containers are also pretty-printed so that there is one item per row. For more details see [String representations](#String%20representations). This is a new feature in Robot Framework 3.1.2.\n\n The old way to control string representation was using the repr argument, and repr=True is still equivalent to using formatter=repr. The repr argument will be deprecated in the future, though, and using formatter is thus recommended.\n\n Examples:\n\n   Log\t Hello, world!\t \t \t \\# Normal INFO message.\t \n  Log\t Warning, world!\t WARN\t \t \\# Warning.\t \n  Log\t <b>Hello</b>, world!\t html=yes\t \t \\# INFO message as HTML.\t \n  Log\t <b>Hello</b>, world!\t HTML\t \t \\# Same as above.\t \n  Log\t <b>Hello</b>, world!\t DEBUG\t html=true\t \\# DEBUG as HTML.\t \n  Log\t Hello, console!\t console=yes\t \t \\# Log also to the console.\t \n  Log\t Null is \\x00\t formatter=repr\t \t \\# Log 'Null is \\x00'.\t \n \n See [Log Many](#Log%20Many) if you want to log multiple messages in one go, and [Log To Console](#Log%20To%20Console) if you only want to write to the console.\n\n",
                "range": {
                    "start": {"line": 5, "character": 4},
                    "end": {"line": 5, "character": 6},
                    "startLineNumber": 3,
                    "startColumn": 1,
                    "endLineNumber": 3,
                    "endColumn": 3,
                },
                "preselect": False,
            }
            break
    else:
        raise AssertionError('Did not find "Log" in the suggestions.')


def test_rf_interactive_integrated_fs_completions(
    language_server_io: ILanguageServerClient,
    rf_interpreter_startup: _RfInterpreterInfo,
    data_regression,
):
    from robocorp_ls_core import uris
    from robocorp_ls_core.workspace import Document

    # Check that we're able to get completions based on the current dir.
    from robotframework_ls.commands import ROBOT_INTERNAL_RFINTERACTIVE_COMPLETIONS
    from robocorp_ls_core.lsp import Position

    uri = rf_interpreter_startup.uri
    fs_path = uris.to_fs_path(uri)
    dirname = os.path.dirname(fs_path)
    with open(os.path.join(dirname, "my_lib_03.py"), "w") as stream:
        stream.write(
            """
def some_method():
    pass
"""
        )

    language_server = language_server_io
    code = "*** Settings ***\nLibrary    ./my_"
    doc = Document(uri, code)
    completions = language_server.execute_command(
        ROBOT_INTERNAL_RFINTERACTIVE_COMPLETIONS,
        [
            {
                "interpreter_id": rf_interpreter_startup.interpreter_id,
                "code": code,
                "position": Position(*doc.get_last_line_col()).to_dict(),
            }
        ],
    )

    suggestions = completions["result"]["suggestions"]
    assert suggestions
    data_regression.check(suggestions)


def test_rf_interactive_integrated_auto_import_completions(
    language_server_io: ILanguageServerClient,
    rf_interpreter_startup: _RfInterpreterInfo,
    data_regression,
):
    from robocorp_ls_core.workspace import Document
    from robotframework_ls_tests.fixtures import check_code_lens_data_regression

    # Check that we're able to get completions based on the current dir.
    from robotframework_ls.commands import ROBOT_INTERNAL_RFINTERACTIVE_COMPLETIONS
    from robocorp_ls_core.lsp import Position

    uri = rf_interpreter_startup.uri

    language_server = language_server_io
    code = "append to lis"
    doc = Document(uri, code)
    completions = language_server.execute_command(
        ROBOT_INTERNAL_RFINTERACTIVE_COMPLETIONS,
        [
            {
                "interpreter_id": rf_interpreter_startup.interpreter_id,
                "code": code,
                "position": Position(*doc.get_last_line_col()).to_dict(),
            }
        ],
    )

    suggestions = completions["result"]["suggestions"]
    assert suggestions
    assert "Adds values to the end of list" in suggestions[0]["documentation"]
    suggestions[0]["documentation"] = "<replaced_for_test>"
    check_code_lens_data_regression(data_regression, suggestions)


def test_code_lens_integrated_rf_interactive(
    language_server_io: ILanguageServerClient, ws_root_path, data_regression
):
    from robocorp_ls_core import uris
    from robotframework_ls_tests.fixtures import check_code_lens_data_regression

    language_server = language_server_io

    language_server.initialize(ws_root_path, process_id=os.getpid())
    uri_untitled = "~untitled"
    txt = """
*** Task ***
Log It
    Log
"""
    language_server.open_doc(uri_untitled, 1, txt)
    ret = language_server.request_code_lens(uri_untitled)
    found = ret["result"]
    assert not found  # when unable to resolve path, we can't create it.

    os.makedirs(ws_root_path, exist_ok=True)
    uri = uris.from_fs_path(os.path.join(ws_root_path, "my.robot"))
    txt = """
*** Task ***
Log It
    Log
"""
    language_server.open_doc(uri, 1, txt)

    ret = language_server.request_code_lens(uri)
    found = ret["result"]
    for code_lens in found:
        if code_lens.get("data", {}).get("type") == "rf_interactive":
            break
    else:
        raise AssertionError(f"Unable to find 'rf_interactive' code lens in: {ret}")
    check_code_lens_data_regression(
        data_regression, [code_lens], basename="code_lens_before_resolve"
    )

    ret = language_server.request_resolve_code_lens(code_lens)
    resolved_code_lens = ret["result"]
    check_code_lens_data_regression(
        data_regression, [resolved_code_lens], basename="code_lens_after_resolve"
    )
