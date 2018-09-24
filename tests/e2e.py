import fcntl
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
import unittest


def cmd(cmdline, env=None):
    retcode = subprocess.call(cmdline, env=env)
    if retcode != 0:
        raise Exception('"{0}" command returned exit code {1}'.format(' '.join(cmdline), retcode))


class E2ETests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.work_dir = os.path.dirname(os.path.realpath(__file__))
        cls.frontend_dir = os.path.join(cls.work_dir, "frontend")
        cls.mobile_dir = os.path.join(cls.frontend_dir, "mobile")
        cls.client_dir = os.path.join(cls.mobile_dir, "client")
        cls.stylist_dir = os.path.join(cls.mobile_dir, "stylist")

        cls.build_mobile_apps()
        cls.run_api_server()

    @classmethod
    def tearDownClass(cls):
        cls.stop_api_server()

    @classmethod
    def prepare_frontend_env(cls, app_dir):
        shutil.copyfile(os.path.join(cls.work_dir, 'environment.e2e.ts'),
                        os.path.join(app_dir, 'src', 'app', 'environments', 'environment.e2e.ts'))
        cls.frontend_env = os.environ.copy()
        cls.frontend_env["MB_ENV"] = "e2e"

    @classmethod
    def build_mobile_apps(cls):
        os.chdir(cls.work_dir)

        # Make sure our SSH key has the right permissions.
        # TODO: encrypt id_rsa file and decrypt during Travis build.
        os.chmod("id_rsa", 0o400)

        # Get frontend source codes
        if (os.path.exists(cls.frontend_dir)):
            # Pull updates
            os.chdir(cls.frontend_dir)
            cmd(["ssh-agent", "bash", "-c", "ssh-add ../id_rsa; git pull"])
        else:
            # Clone the repo
            cmd(["ssh-agent", "bash", "-c", "ssh-add ./id_rsa; git clone git@github.com:madebeauty/frontend.git"])

        # Build frontend
        cls.prepare_frontend_env(cls.client_dir)
        cls.prepare_frontend_env(cls.stylist_dir)

        os.chdir(cls.mobile_dir)
        cmd(["make", "build-fast-client", "build-fast-stylist", "-j8"], env=cls.frontend_env)

    @classmethod
    def is_api_server_running(cls):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.connect(("0.0.0.0", 8000))
            s.close()
            return True
        except:
            s.close()
            return False

    @classmethod
    def run_api_server(cls):
        if cls.is_api_server_running():
            raise Exception('API server is already running, stop it before starting these tests.')

        print('Starting API server...')

        # Build and run API server
        os.chdir(os.path.join(cls.work_dir, ".."))

        server_env = os.environ.copy()
        server_env["LEVEL"] = "tests"
        server_env["DJANGO_SETTINGS_MODULE"] = "core.settings.tests"

        # TODO: Make E2E tests read backdoor API key from environment.*.ts and generate a random
        # key here instead of hard-coding it (currently also hard-coded in E2E tests).
        server_env["BACKDOOR_API_KEY"] = "z7NdGmXDcncz5Ht4D6P4m"

        # Start the subprocess. Note: we use os.setsid to run the subprocess and its
        # children in a separate process group. This is neccessary so that we can
        # later kill the entire group at once without killing ourselves.
        # (Solution inspired by: https://stackoverflow.com/a/22582602)
        proc = subprocess.Popen(["make", "run"], env=server_env, preexec_fn=os.setsid)
        cls.server_proc = proc

        # Wait until we can connect to it
        start_time = time.time()
        while time.time() - start_time < 10:
            if cls.is_api_server_running():
                print('\nAPI server is running.')
                return
            else:
                time.sleep(0.1)

        raise Exception('\nCould not start API server.')

    @classmethod
    def stop_api_server(cls):
        print('\nStopping API server, sending SIGTERM to make, you can ignore the next failure message from make...')
        os.killpg(os.getpgid(cls.server_proc.pid), signal.SIGTERM)
        cls.server_proc.wait()
        print('API server stopped.')

    def test_stylist_app(self):
        print('Begin running Stylist App E2E tests.')
        os.chdir(self.stylist_dir)
        cmd(["npm", "run", "e2e-test"], env=self.frontend_env)

    def test_client_app(self):
        print('Begin running Client App E2E tests.')
        os.chdir(self.client_dir)
        cmd(["npm", "run", "e2e-test"], env=self.frontend_env)


if __name__ == '__main__':
    unittest.main()
