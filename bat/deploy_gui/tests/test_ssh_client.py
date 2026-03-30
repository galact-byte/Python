from deploy_gui.models import CommandResult


def test_build_remote_command_result_without_network():
    result = CommandResult(command="echo ok", exit_code=0, stdout="ok", stderr="")
    assert result.ok is True
