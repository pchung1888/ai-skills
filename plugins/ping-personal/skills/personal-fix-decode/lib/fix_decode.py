#!/usr/bin/env python3
"""fix_decode.py -- decode a raw FIX 4.4 message into a readable tag table.

Usage:
    python fix_decode.py <file>          # file containing one or more messages
    python fix_decode.py - < file        # stdin
    python fix_decode.py <file> --json   # machine-readable output

Accepts SOH (\\x01), '|', or '^A' as field delimiters. ASCII-only output.
Unknown tags are printed as 'tag <n> (unknown)' -- never guessed.
"""
import argparse
import json
import sys

TAGS = {
    1: "Account", 6: "AvgPx", 8: "BeginString", 9: "BodyLength", 10: "CheckSum",
    11: "ClOrdID", 14: "CumQty", 15: "Currency", 17: "ExecID", 22: "SecurityIDSource",
    30: "LastMkt", 31: "LastPx", 32: "LastQty", 34: "MsgSeqNum", 35: "MsgType",
    37: "OrderID", 38: "OrderQty", 39: "OrdStatus", 40: "OrdType", 41: "OrigClOrdID",
    44: "Price", 45: "RefSeqNum", 48: "SecurityID", 49: "SenderCompID",
    50: "SenderSubID", 52: "SendingTime", 54: "Side", 55: "Symbol", 56: "TargetCompID",
    57: "TargetSubID", 58: "Text", 59: "TimeInForce", 60: "TransactTime",
    64: "SettlDate", 70: "AllocID", 71: "AllocTransType", 73: "NoOrders",
    75: "TradeDate", 78: "NoAllocs", 79: "AllocAccount", 80: "AllocQty",
    97: "PossResend", 98: "EncryptMethod", 102: "CxlRejReason", 103: "OrdRejReason",
    108: "HeartBtInt", 112: "TestReqID", 115: "OnBehalfOfCompID", 116: "OnBehalfOfSubID",
    122: "OrigSendingTime", 128: "DeliverToCompID", 141: "ResetSeqNumFlag",
    150: "ExecType", 151: "LeavesQty", 167: "SecurityType", 198: "SecondaryOrderID",
    207: "SecurityExchange", 223: "CouponRate", 228: "Factor", 231: "ContractMultiplier",
    236: "Yield", 320: "SecurityReqID", 336: "TradingSessionID", 371: "RefTagID",
    372: "RefMsgType", 373: "SessionRejectReason", 380: "BusinessRejectReason",
    381: "GrossTradeAmt", 423: "PriceType", 447: "PartyIDSource", 448: "PartyID",
    452: "PartyRole", 453: "NoPartyIDs", 454: "NoSecurityAltID", 455: "SecurityAltID",
    456: "SecurityAltIDSource", 487: "TradeReportTransType", 523: "PartySubID",
    528: "OrderCapacity", 552: "NoSides", 555: "NoLegs", 571: "TradeReportID",
    568: "TradeRequestID", 570: "PreviouslyReported", 573: "MatchStatus",
    577: "ClearingInstruction", 581: "AccountType", 625: "TradingSessionSubID",
    715: "ClearingBusinessDate", 748: "TotNumTradeReports", 768: "NoTrdRegTimestamps",
    769: "TrdRegTimestamp", 770: "TrdRegTimestampType", 802: "NoPartySubIDs",
    803: "PartySubIDType", 828: "TrdType", 856: "TradeReportType", 880: "TrdMatchID",
}

MSG_TYPES = {
    "0": "Heartbeat", "1": "TestRequest", "2": "ResendRequest", "3": "SessionReject",
    "4": "SequenceReset", "5": "Logout", "8": "ExecutionReport",
    "9": "OrderCancelReject", "A": "Logon", "D": "NewOrderSingle",
    "F": "OrderCancelRequest", "G": "OrderCancelReplaceRequest",
    "J": "AllocationInstruction", "P": "AllocationInstructionAck",
    "AE": "TradeCaptureReport", "AR": "TradeCaptureReportAck",
    "AD": "TradeCaptureReportRequest", "j": "BusinessMessageReject",
}

ENUMS = {
    54: {"1": "Buy", "2": "Sell", "5": "SellShort"},
    39: {"0": "New", "1": "PartiallyFilled", "2": "Filled", "4": "Canceled",
         "8": "Rejected", "A": "PendingNew"},
    150: {"0": "New", "4": "Canceled", "8": "Rejected", "F": "Trade"},
    452: {"1": "ExecutingFirm", "3": "ClientID", "11": "OrderOriginationTrader",
          "12": "ExecutingTrader", "13": "OrderOriginationFirm", "17": "ContraFirm",
          "27": "BuyAgent", "28": "SellAgent"},
    447: {"B": "BIC", "C": "AcceptedMarketParticipant", "D": "ProprietaryCustomCode"},
    373: {"0": "InvalidTagNumber", "1": "RequiredTagMissing",
          "2": "TagNotDefinedForThisMessageType", "3": "UndefinedTag",
          "4": "TagSpecifiedWithoutAValue", "5": "ValueIsIncorrect",
          "6": "IncorrectDataFormatForValue", "9": "CompIDProblem",
          "10": "SendingTimeAccuracyProblem", "11": "InvalidMsgType"},
    380: {"0": "Other", "1": "UnknownID", "2": "UnknownSecurity",
          "3": "UnsupportedMessageType", "4": "ApplicationNotAvailable",
          "5": "ConditionallyRequiredFieldMissing", "6": "NotAuthorized"},
}


def split_fields(raw: str) -> list[tuple[int, str]]:
    raw = raw.strip()
    for delim in ("\x01", "^A", "|"):
        if delim in raw:
            parts = raw.split(delim)
            break
    else:
        parts = raw.split()
    fields = []
    for p in parts:
        p = p.strip()
        if not p or "=" not in p:
            continue
        tag_s, _, value = p.partition("=")
        try:
            fields.append((int(tag_s), value))
        except ValueError:
            continue
    return fields


def checksum_warnings(raw: str, fields: list[tuple[int, str]]) -> list[str]:
    warnings = []
    tags = dict(fields)
    if 9 in tags:
        # BodyLength = bytes between the field after 9 and the start of tag 10.
        # We can only verify when the SOH delimiter was preserved.
        if "\x01" in raw:
            try:
                start = raw.index("\x01", raw.index("9=")) + 1
                end = raw.index("10=")
                actual = len(raw[start:end].encode("ascii", errors="replace"))
                if actual != int(tags[9]):
                    warnings.append(
                        f"BodyLength(9) says {tags[9]} but measured {actual}")
            except (ValueError, KeyError):
                pass
    if 10 in tags and "\x01" in raw:
        try:
            end = raw.index("10=")
            total = sum(raw[:end].encode("ascii", errors="replace")) % 256
            if f"{total:03d}" != tags[10].strip():
                warnings.append(
                    f"CheckSum(10) says {tags[10]} but computed {total:03d}")
        except ValueError:
            pass
    return warnings


def decode(raw: str) -> dict:
    fields = split_fields(raw)
    if not fields:
        raise ValueError("no tag=value fields found (is this a FIX message?)")
    rows = []
    for tag, value in fields:
        name = TAGS.get(tag)
        if name is None:
            name = f"(unknown{' custom' if tag >= 5000 else ''})"
        decoded = ""
        if tag == 35:
            decoded = MSG_TYPES.get(value, "(unknown MsgType)")
        elif tag in ENUMS:
            decoded = ENUMS[tag].get(value, "")
        rows.append({"tag": tag, "name": name, "value": value, "decoded": decoded})
    tags = dict(fields)
    return {
        "msg_type": tags.get(35, ""),
        "msg_type_name": MSG_TYPES.get(tags.get(35, ""), "(unknown MsgType)"),
        "fields": rows,
        "warnings": checksum_warnings(raw, fields),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("source", help="file path, or - for stdin")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    raw = sys.stdin.read() if a.source == "-" else open(
        a.source, encoding="ascii", errors="replace").read()
    try:
        result = decode(raw)
    except ValueError as e:
        print(f"DECODE-FAIL: {e}", file=sys.stderr)
        return 2
    if a.json:
        print(json.dumps(result, indent=2))
        return 0
    print(f"MsgType: {result['msg_type']} = {result['msg_type_name']}")
    print(f"{'tag':>6}  {'name':<28} value")
    for r in result["fields"]:
        suffix = f"  [{r['decoded']}]" if r["decoded"] else ""
        print(f"{r['tag']:>6}  {r['name']:<28} {r['value']}{suffix}")
    for w in result["warnings"]:
        print(f"WARNING: {w}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
