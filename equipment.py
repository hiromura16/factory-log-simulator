"""Real OPC UA and Modbus TCP servers, driven by one deterministic equipment model."""

import asyncio
import json
import os
import struct
from functools import partial
from datetime import datetime, timezone
from connection_security import connection_file


def encode_register(value, mapping):
    if mapping.enum_values:
        value = mapping.enum_values.get(str(value))
    if value is None:
        raise ValueError("値が欠測またはenum対応表にありません")
    if mapping.encoding == "bool":
        return [bool(value)]
    value = float(value) * mapping.scale + mapping.offset
    formats = {
        "uint16": "H",
        "int16": "h",
        "uint32": "I",
        "int32": "i",
        "float32": "f",
        "float64": "d",
    }
    code = formats[mapping.encoding]
    raw = struct.pack(">" + code, value if code in {"f", "d"} else int(value))
    words = [raw[i : i + 2] for i in range(0, len(raw), 2)]
    if mapping.byte_order == "little":
        words = [w[::-1] for w in words]
    if mapping.word_order == "little":
        words.reverse()
    return [int.from_bytes(w, "big") for w in words]


class EquipmentDriver:
    def __init__(self, c):
        self.c = c
        self.opc = None
        self.modbus = None
        self.nodes = {}
        self.values = {}
        self.offline = False
        self.information = {}
        self.overrides = {}

    async def start(self):
        for device in range(1, self.c.spec.equipment.devices + 1):
            self.values[device] = self.c.record(device - 1)
        await self.open()

    async def open(self):
        from asyncua import Server, ua
        from asyncua.server.user_managers import User, UserRole
        from pymodbus.server import ModbusTcpServer
        from pymodbus.simulator import SimDevice, SimData, DataType

        p = self.c.profile
        options = self.c.spec.equipment
        if p.opc_enabled:

            class Manager:
                def get_user(
                    self, iserver, username=None, password=None, certificate=None
                ):
                    if p.opc_auth == "anonymous" and not username:
                        return User(role=UserRole.User)
                    import hmac

                    if (
                        p.opc_auth == "username"
                        and username == p.opc_username
                        and p.opc_password
                        and hmac.compare_digest(
                            password or "", p.opc_password.get_secret_value()
                        )
                    ):
                        return User(role=UserRole.User)
                    return None

            server = Server(user_manager=Manager())
            await server.init()
            server.set_endpoint(f"opc.tcp://0.0.0.0:{p.opc_port}/factory/")
            await server.set_application_uri(p.namespace_uri)
            server.set_server_name("Factory Equipment Simulator")
            if p.opc_security == "sign_encrypt":
                if not p.certificate_file or not p.private_key_file:
                    raise ValueError("OPC UAの証明書と秘密鍵を配置してください")
                await server.load_certificate(connection_file(p.certificate_file))
                await server.load_private_key(connection_file(p.private_key_file))
                from cryptography import x509
                from cryptography.hazmat.primitives import hashes

                if not p.trusted_client_certificates:
                    raise ValueError("信頼するクライアント証明書を指定してください")
                trusted = set()
                for path in p.trusted_client_certificates:
                    data = (
                        __import__("pathlib").Path(connection_file(path)).read_bytes()
                    )
                    cert = (
                        x509.load_pem_x509_certificate(data)
                        if data.startswith(b"-----")
                        else x509.load_der_x509_certificate(data)
                    )
                    trusted.add(cert.fingerprint(hashes.SHA256()))

                async def validate_certificate(cert, application):
                    if cert.fingerprint(hashes.SHA256()) not in trusted:
                        raise ua.UaStatusCodeError(
                            ua.StatusCodes.BadCertificateUntrusted
                        )
                    now = datetime.now(timezone.utc)
                    if not cert.not_valid_before_utc <= now <= cert.not_valid_after_utc:
                        raise ua.UaStatusCodeError(
                            ua.StatusCodes.BadCertificateTimeInvalid
                        )

                server.set_certificate_validator(validate_certificate)
                server.set_security_policy(
                    [ua.SecurityPolicyType.Basic256Sha256_SignAndEncrypt]
                )
            else:
                server.set_security_policy([ua.SecurityPolicyType.NoSecurity])
            server.set_identity_tokens(
                [ua.AnonymousIdentityToken]
                if p.opc_auth == "anonymous"
                else [ua.UserNameIdentityToken]
            )
            namespace = await server.register_namespace(p.namespace_uri)
            self.nodes = {}
            for device, row in self.values.items():
                obj = await server.nodes.objects.add_object(
                    ua.NodeId(f"Device{device:03d}", namespace), f"Device{device:03d}"
                )
                for field in self.c.spec.generator.fields:
                    value = row.get(field.name)
                    variant = self.variant(field, value)
                    node = await obj.add_variable(
                        ua.NodeId(f"Device{device:03d}.{field.name}", namespace),
                        field.name,
                        variant,
                    )
                    if options.writable:
                        await node.set_writable()
                    self.nodes[device, field.name] = node
            await server.start()
            self.opc = server
            self.information["opc_ua"] = {
                "endpoint": f"opc.tcp://HOST:{os.environ.get('PUBLIC_OPC_PORT', p.opc_port)}/factory/",
                "namespace_uri": p.namespace_uri,
                "namespace_index": namespace,
                "node_id_example": f"ns={namespace};s=Device001.value",
            }
        if p.modbus_enabled:
            devices = []
            for device in range(1, options.devices + 1):
                blocks = []
                for area in ["coil", "discrete", "holding", "input"]:
                    entries = []
                    for mapping in options.registers:
                        if mapping.area != area:
                            continue
                        width = {
                            "uint32": 2,
                            "int32": 2,
                            "float32": 2,
                            "float64": 4,
                        }.get(mapping.encoding, 1)
                        entries.append(
                            SimData(
                                mapping.address,
                                values=[False] * width
                                if area in {"coil", "discrete"}
                                else [0] * width,
                                datatype=DataType.BITS
                                if area in {"coil", "discrete"}
                                else DataType.REGISTERS,
                                readonly=not options.writable,
                            )
                        )
                    blocks.append(
                        entries
                        or [
                            SimData(
                                65535,
                                values=False if area in {"coil", "discrete"} else 0,
                                datatype=DataType.BITS
                                if area in {"coil", "discrete"}
                                else DataType.REGISTERS,
                                readonly=True,
                            )
                        ]
                    )
                devices.append(
                    SimDevice(
                        device,
                        simdata=tuple(blocks),
                        action=partial(self.access, device),
                    )
                )
            self.modbus = ModbusTcpServer(devices, address=("0.0.0.0", p.modbus_port))
            await self.modbus.serve_forever(background=True)
            self.information["modbus"] = {
                "port": int(os.environ.get("PUBLIC_MODBUS_PORT", p.modbus_port)),
                "device_ids": list(self.values),
                "address_base": 0,
                "mappings": [m.model_dump() for m in options.registers],
            }

    def variant(self, field, value):
        from asyncua import ua

        types = {
            "integer": ua.VariantType.Int64,
            "number": ua.VariantType.Double,
            "decimal": ua.VariantType.Double,
            "boolean": ua.VariantType.Boolean,
            "datetime": ua.VariantType.DateTime,
            "string": ua.VariantType.String,
            "json": ua.VariantType.String,
        }
        dtype = types[field.data_type]
        if value is None:
            value = {
                "integer": 0,
                "number": 0.0,
                "decimal": 0.0,
                "boolean": False,
                "datetime": datetime.now(timezone.utc),
            }.get(field.data_type, "")
        elif field.data_type == "datetime":
            value = datetime.fromisoformat(str(value))
        elif field.data_type in {"number", "decimal"}:
            value = float(value)
        elif field.data_type == "json":
            value = json.dumps(value, ensure_ascii=False)
        return ua.Variant(value, dtype)

    async def access(
        self, device, code, start, address, count, registers, write_values
    ):
        from pymodbus.constants import ExcCodes

        options = self.c.spec.equipment
        if options.read_delay_ms:
            await asyncio.sleep(options.read_delay_ms / 1000)
        area = (
            "coil"
            if code in {1, 5, 15}
            else "discrete"
            if code == 2
            else "input"
            if code == 4
            else "holding"
        )
        if write_values is not None:
            if not options.writable:
                return ExcCodes.ILLEGAL_FUNCTION
            self.overrides[device, area, address] = (self.c.tick, list(write_values))
            return None
        try:
            for mapping in options.registers:
                if mapping.area != area:
                    continue
                values = encode_register(
                    self.values[device].get(mapping.field), mapping
                )
                if area in {"coil", "discrete"}:
                    # Distinct bit blocks are internally packed by PyModbus.
                    for i, value in enumerate(values):
                        bit = mapping.address + i - start * 16
                        word = bit // 16
                        if 0 <= word < len(registers):
                            registers[word] = (
                                (registers[word] | (1 << (bit % 16)))
                                if value
                                else (registers[word] & ~(1 << (bit % 16)))
                            )
                else:
                    offset = mapping.address - start
                    if 0 <= offset and offset + len(values) <= len(registers):
                        registers[offset : offset + len(values)] = values
            for (d, a, addr), (tick, values) in self.overrides.items():
                if (
                    d == device
                    and a == area
                    and tick == self.c.tick
                    and area not in {"coil", "discrete"}
                ):
                    registers[addr - start : addr - start + len(values)] = values
        except (ValueError, TypeError, OverflowError, struct.error):
            return ExcCodes.DEVICE_FAILURE
        return None

    async def step(self, tick):
        from asyncua import ua

        opts = self.c.spec.equipment
        down = bool(
            opts.offline_from_tick
            and opts.offline_from_tick
            <= tick
            < opts.offline_from_tick + opts.offline_ticks
        )
        if down and not self.offline:
            await self.close()
            self.offline = True
        elif not down and self.offline:
            self.offline = False
            await self.open()
        for device in self.values:
            row = self.c.record(tick * opts.devices + device - 1)
            self.values[device] = row
            self.c.observe({"device_id": device, **row})
            if self.offline:
                continue
            if self.opc:
                bad = (
                    opts.quality != "Good"
                    and tick >= opts.quality_from_tick
                    and (not opts.quality_until_tick or tick <= opts.quality_until_tick)
                )
                status = (
                    getattr(ua.StatusCodes, opts.quality)
                    if bad
                    else ua.StatusCodes.Good
                )
                for field in self.c.spec.generator.fields:
                    try:
                        variant = self.variant(field, row.get(field.name))
                        code = (
                            ua.StatusCodes.BadNoData
                            if row.get(field.name) is None
                            else status
                        )
                    except (ValueError, TypeError):
                        variant = self.variant(field, None)
                        code = ua.StatusCodes.BadTypeMismatch
                    value = ua.DataValue(
                        variant,
                        ua.StatusCode(code),
                        SourceTimestamp=datetime.now(timezone.utc),
                    )
                    await self.nodes[device, field.name].write_value(value)

    async def close(self):
        if self.modbus:
            await self.modbus.shutdown()
            self.modbus = None
        if self.opc:
            await self.opc.stop()
            self.opc = None
