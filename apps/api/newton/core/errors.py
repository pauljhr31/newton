"""Uniform API errors: a stable machine `code` plus a French `message` for the UI."""

from fastapi import HTTPException


def api_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "message": message})
