"""Minimal MPU-6050 (GY-521) driver for MicroPython over I2C."""

from machine import I2C, Pin
import math
import time
import struct

# Register map
_PWR_MGMT_1 = 0x6B
_SMPLRT_DIV = 0x19
_CONFIG = 0x1A
_GYRO_CONFIG = 0x1B
_ACCEL_CONFIG = 0x1C
_ACCEL_XOUT_H = 0x3B
_WHO_AM_I = 0x75

# ±2g => 16384 LSB/g
_ACCEL_SCALE = 16384.0


class MPU6050:
    def __init__(self, i2c, addr=0x68):
        self.i2c = i2c
        self.addr = addr
        who = self.i2c.readfrom_mem(self.addr, _WHO_AM_I, 1)[0]
        if who not in (0x68, 0x72, 0x98):
            raise OSError("Unexpected MPU WHO_AM_I: 0x%02x" % who)

        # Wake device, set sample rate / DLPF, ±2g accel
        self.i2c.writeto_mem(self.addr, _PWR_MGMT_1, b"\x00")
        time.sleep_ms(50)
        self.i2c.writeto_mem(self.addr, _SMPLRT_DIV, b"\x07")
        self.i2c.writeto_mem(self.addr, _CONFIG, b"\x06")
        self.i2c.writeto_mem(self.addr, _GYRO_CONFIG, b"\x00")
        self.i2c.writeto_mem(self.addr, _ACCEL_CONFIG, b"\x00")
        time.sleep_ms(20)

    def accel_g(self):
        raw = self.i2c.readfrom_mem(self.addr, _ACCEL_XOUT_H, 6)
        ax, ay, az = struct.unpack(">hhh", raw)
        return (
            ax / _ACCEL_SCALE,
            ay / _ACCEL_SCALE,
            az / _ACCEL_SCALE,
        )

    def vibration_magnitude(self):
        """Absolute acceleration magnitude in g (includes gravity ~1.0)."""
        ax, ay, az = self.accel_g()
        return math.sqrt(ax * ax + ay * ay + az * az)

    def vibration_level(self):
        """Deviation from 1g — useful as a vibration proxy while sitting still on a machine."""
        return abs(self.vibration_magnitude() - 1.0)


def _i2c_id_for_pins(sda, scl):
    # RP2040 I2C0 / I2C1 valid pin sets
    i2c0 = {0, 1, 4, 5, 8, 9, 12, 13, 16, 17, 20, 21}
    i2c1 = {2, 3, 6, 7, 10, 11, 14, 15, 18, 19, 26, 27}
    if sda in i2c0 and scl in i2c0:
        return 0
    if sda in i2c1 and scl in i2c1:
        return 1
    raise ValueError("Pins SDA=%s SCL=%s are not a valid I2C pair" % (sda, scl))


def make_mpu(cfg):
    sda = int(cfg["i2c_sda"])
    scl = int(cfg["i2c_scl"])
    freq = int(cfg.get("i2c_freq", 400000))
    addr = int(cfg.get("mpu_addr", 0x68))
    i2c = I2C(
        _i2c_id_for_pins(sda, scl),
        sda=Pin(sda),
        scl=Pin(scl),
        freq=freq,
    )
    found = i2c.scan()
    if addr not in found:
        found_hex = " ".join("0x%02x" % a for a in found) or "(none)"
        raise OSError(
            "MPU not responding at 0x%02x on SDA=GP%d SCL=GP%d @ %d Hz; "
            "I2C scan=%s. Check VCC=3V3, GND, SDA/SCL wiring, and AD0→GND "
            "for address 0x68."
            % (addr, sda, scl, freq, found_hex)
        )
    try:
        return MPU6050(i2c, addr=addr)
    except OSError as exc:
        raise OSError(
            "MPU present at 0x%02x but init failed on SDA=GP%d SCL=GP%d: %s"
            % (addr, sda, scl, exc)
        )
