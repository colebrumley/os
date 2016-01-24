import string
import subprocess

import pytest
import rostest.util as u
from rostest.util import SSH
import yaml

ssh_command = ['./scripts/ssh', '--qemu', '--key', './tests/integration/assets/test.key']
cloud_config_path = './tests/integration/assets/test_01/cloud-config.yml'


@pytest.fixture(scope="module")
def qemu(request):
    q = u.run_qemu(request, ['--cloud-config', cloud_config_path,
                             '-net', 'nic,vlan=1,model=virtio', '-net', 'user,vlan=1,net=10.10.2.0/24'])
    u.flush_out(q.stdout)
    return q


@pytest.fixture(scope="module")
def cloud_config():
    return yaml.load(open(cloud_config_path))


@pytest.mark.timeout(40)
def test_ssh_authorized_keys(qemu):
    u.wait_for_ssh(qemu, ssh_command)
    assert True


@pytest.mark.timeout(40)
def test_rancher_environment(qemu, cloud_config):
    u.wait_for_ssh(qemu, ssh_command)

    v = subprocess.check_output(
        ssh_command + ['sudo', 'ros', 'env', 'printenv', 'FLANNEL_NETWORK'],
        stderr=subprocess.STDOUT, universal_newlines=True)

    assert v.strip() == cloud_config['rancher']['environment']['FLANNEL_NETWORK']


@pytest.mark.timeout(40)
def test_docker_args(qemu, cloud_config):
    u.wait_for_ssh(qemu, ssh_command)

    v = subprocess.check_output(
        ssh_command + ['sh', '-c', 'ps -ef | grep docker'],
        stderr=subprocess.STDOUT, universal_newlines=True)

    expected = string.join(cloud_config['rancher']['docker']['args'])

    assert v.find(expected) != -1


@pytest.mark.timeout(40)
def test_dhcpcd(qemu, cloud_config):
    u.wait_for_ssh(qemu, ssh_command)

    v = subprocess.check_output(
        ssh_command + ['sh', '-c', 'ps -ef | grep dhcpcd'],
        stderr=subprocess.STDOUT, universal_newlines=True)

    assert v.find('dhcpcd -M') != -1


@pytest.mark.timeout(40)
def test_services_include(qemu, cloud_config):
    u.wait_for_ssh(qemu, ssh_command, ['docker inspect kernel-headers >/dev/null 2>&1'])


@pytest.mark.timeout(40)
def test_docker_tls_args(qemu, cloud_config):
    u.wait_for_ssh(qemu, ssh_command)

    subprocess.check_call(
        ssh_command + ['sudo', 'ros', 'tls', 'gen'],
        stderr=subprocess.STDOUT, universal_newlines=True)

    subprocess.check_call(
        ssh_command + ['docker', '--tlsverify', 'version'],
        stderr=subprocess.STDOUT, universal_newlines=True)


@pytest.mark.timeout(40)
def test_rancher_network(qemu, cloud_config):
    u.wait_for_ssh(qemu, ssh_command)

    v = subprocess.check_output(
        ssh_command + ['ip', 'route', 'get', 'to', '10.10.2.120'],
        stderr=subprocess.STDOUT, universal_newlines=True)

    assert v.split(' ')[2] == 'eth1'
    assert v.split(' ')[5] + '/24' == cloud_config['rancher']['network']['interfaces']['eth1']['address']


def test_docker_not_pid_one(qemu):
    SSH(qemu, ssh_command=ssh_command).check_call('bash', '-c', '''
    set -e -x
    for i in $(pidof docker); do
        [ $i != 1 ]
    done
    '''.strip())
