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
        cls.frontend_dir = os.path.join(cls.work_dir,"frontend")
        cls.mobile_dir = os.path.join(cls.frontend_dir,"mobile")
        cls.client_dir = os.path.join(cls.mobile_dir,"client")
        cls.stylist_dir = os.path.join(cls.mobile_dir,"stylist")

        cls.build_mobile_apps()
        cls.run_api_server()

    @classmethod
    def tearDownClass(cls):
        cls.stop_api_server()

    @classmethod
    def prepare_frontend_env(cls, app_dir):
        shutil.copyfile(os.path.join(cls.work_dir, 'environment.e2e.ts'), os.path.join(app_dir, 'src', 'environments', 'environment.e2e.ts'))
        cls.frontend_env = os.environ.copy()
        cls.frontend_env["MB_ENV"] = "e2e"

    @classmethod
    def build_mobile_apps(cls):
        # Get frontend source codes
        if (os.path.exists(cls.frontend_dir)):
            os.chdir(cls.frontend_dir)
            cmd(["git","pull"])
        else:
            cmd(["git","clone", "git@github.com:madebeauty/frontend.git"])

        # Build frontend
        os.chdir(cls.mobile_dir)
        cmd(["make","preinstall-stylist","preinstall-client","-j8"])

        cls.prepare_frontend_env(cls.stylist_dir)

        os.chdir(cls.stylist_dir)
        cmd(["npm","run","build"], env=cls.frontend_env)

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
            print('API server is already running, stop it before starting these tests.')
            raise Exception()

        print('Starting API server...')

        # Build and run API server
        os.chdir(os.path.join(cls.work_dir,".."))
        proc = subprocess.Popen(["make","run"])
        cls.server_proc = proc

        # Wait until we can connect to it
        start_time = time.time()
        while time.time() - start_time < 10:
            if cls.is_api_server_running():
                print('\nAPI server is running.')
                return
            else:
                time.sleep(0.1)

        print('\nCould not start API server.')
        raise Exception()

    @classmethod
    def stop_api_server(cls):
        print('\nStopping API server, sending SIGINT to make, you can ignore the next failure message from make...')
        pgrp = os.getpgid(cls.server_proc.pid)
        try:
            os.killpg(pgrp, signal.SIGINT)
        except KeyboardInterrupt:
            # Ignore our own signal
            pass
        cls.server_proc.wait()
        print('API server stopped.')

    def test_stylist_app(self):
        print('Begin running Stylist App E2E tests.')
        os.chdir(self.stylist_dir)
        cmd(["npm","run","e2e-test"])

if __name__ == '__main__':
    unittest.main()
