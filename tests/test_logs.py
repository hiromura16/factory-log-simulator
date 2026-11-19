"""一時的なUDP・TCP受信ソケットで模擬syslogの実送信を検証する。"""

import asyncio
import socket
import threading
from models import Profile, Spec
from store import Store
from controller import Controller
from drivers import EventDriver


def test_syslog_udp_rfc5424_and_tcp_octet_framing(tmp_path):
    """UDPのRFC 5424メッセージとTCPの長さ接頭辞を検証する。"""

    async def run():
        """ループバック宛てにUDPとTCPでログを一件ずつ送信する。

        UDPでは形式と送達記録、TCPでは接頭辞のバイト数が本文長に
        等しいことを確認する。
        """
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as receiver:
            receiver.bind(("127.0.0.1", 0))
            receiver.settimeout(2)
            store = Store(tmp_path / "udp")
            c = Controller("logs", store)
            c.spec = Spec(batch_size=1)
            c.profile = Profile(
                output="udp", host="127.0.0.1", port=receiver.getsockname()[1]
            )
            d = EventDriver(c)
            await d.start()
            await d.step(0)
            data, _ = receiver.recvfrom(65535)
            assert data.startswith(b"<134>1 ") and "entity=" in data.decode()
            with store.db() as db:
                assert (
                    db.execute(
                        "select count(*) from events where status='delivered'"
                    ).fetchone()[0]
                    == 1
                )
            await d.close()
        with socket.socket() as receiver:
            receiver.bind(("127.0.0.1", 0))
            receiver.listen()
            receiver.settimeout(2)
            received = []

            def accept():
                """別スレッドでTCP接続を一件受け、受信したバイト列を記録する。"""
                conn, _ = receiver.accept()
                with conn:
                    received.append(conn.recv(65535))

            t = threading.Thread(target=accept)
            t.start()
            c.profile = Profile(
                output="tcp", host="127.0.0.1", port=receiver.getsockname()[1]
            )
            d = EventDriver(c)
            await d.start()
            await d.step(1)
            t.join(3)
            size, body = received[0].split(b" ", 1)
            assert int(size) == len(body) and body.startswith(b"<134>1 ")
            await d.close()

    asyncio.run(run())
