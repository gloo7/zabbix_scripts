import sys
from ipaddress import IPv4Address, IPv6Address
from pathlib import Path
from typing import Union, Optional, Dict

from logger import logger
from task._typing import D, Collector
from task.const import FileMatchChoice, MethodChoice


def match_file(dir: Path, filename: str, match: FileMatchChoice) -> Path:
    if not dir.is_dir():
        logger.error(f'{dir} is not exists.')
        sys.exit(1)

    file: Path
    if match == FileMatchChoice.strict:
        file = dir / filename
    else:
        try:
            files = dir.glob(filename)
            _, file = max((f.stat().st_ctime, f) for f in files)
        except ValueError:
            logger.error('No match to file.')
            sys.exit(1)
    if not file.is_file():
        logger.error('Not a file.')
        sys.exit(1)
    return file


def local_collector(*args, dir: Path, filename: str, match: FileMatchChoice = FileMatchChoice.strict, **kwargs) -> Collector:
    file = match_file(dir, filename, match)

    def inner() -> D:
        return dict(message=file.read_text())
    return inner


def ftp_collector(*args, host: Union[IPv4Address, IPv6Address], port: int, user: str, password: str, dir: Path,
                  filename: str, match: FileMatchChoice, **kwargs) -> Collector:
    from ftplib import FTP
    ftp = FTP()
    ftp.set_debuglevel(2)
    ftp.connect(str(host), port)
    ftp.login(user, password)
    file = match_file(dir, filename, match)

    def inner() -> D:
        data = dict(
            message=file.read_text(),
            host=host
        )
        ftp.quit()
        return data
    return inner


def cmd_collector(*args, command: str, **kwargs):
    import subprocess

    def inner() -> D:
        result = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return dict(message=str(result))
    return inner


def mysql_collector(*args, host: Union[IPv4Address, IPv6Address], port: int, user: str, password: str, charset: str,
                    sql: str, **kwargs) -> Collector:
    import pymysql
    conn = pymysql.connect(host=str(host), port=port,
                           user=user, password=password, charset=charset)

    def inner() -> D:
        with conn.cursor() as cursor:
            cursor.excute(sql)
            result = cursor.fetchone()
        return result.update({
            'message': '',
            'host': host,
        })
    return inner


def ssh_collector(*args, host: Union[IPv4Address, IPv6Address], port: int, user: str, password: str, command: str,
                  **kwargs) -> Collector:
    import paramiko
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(str(host), port, user, password, timeout=10)

    def inner() -> D:
        stdin, stdout, stderr = ssh.exec_command(command)
        result = str(stdout.read())
        ssh.close()
        return dict(
            host=host,
            message=result
        )
    return inner


def api_collector(*args, method: MethodChoice, url: str, json_data: Optional[dict] = None, data: Optional[dict] = None,
                  index: Optional[str] = None, headers: Optional[dict] = None, **kwargs) -> Collector:
    import requests

    def inner() -> D:
        resp = requests.request(method, url=url, json=json_data, data=data, headers=headers)
        assert resp.status_code == 200
        temp = resp.json()
        if index is not None:
            ins = index.split('.')
            for i in ins:
                temp = temp[i]
        return temp

    return inner


collector_mapping = {k.replace('_collector', ''): globals(
)[k] for k in globals() if k.endswith('_collector')}
