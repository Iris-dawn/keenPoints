"""MinerU API client for PDF processing."""

import io
import os
import asyncio
import zipfile
from pathlib import Path
from typing import List, Optional

import aiohttp

from app.core.config import settings
from app.core.logger import logger

TAG = "[MINERU]"


async def _apply_urls(session: aiohttp.ClientSession, files: List[str]) -> tuple:
    """Request upload URLs from MinerU."""
    payload = {
        "files": [{"name": os.path.basename(f), "data_id": os.path.basename(f)} for f in files],
        "model_version": settings.MINERU_MODEL,
    }
    async with session.post(
        settings.MINERU_UPLOAD_URL, headers=settings.MINERU_HEADERS, json=payload
    ) as resp:
        result = await resp.json()
        if result.get("code") != 0:
            raise Exception(f"Apply URL failed: {result}")
        data = result["data"]
        logger.info(f"{TAG} urls applied: batch_id={data['batch_id']}")
        return data["batch_id"], data["file_urls"]


async def _upload(session: aiohttp.ClientSession, file_path: str, url: str):
    """Upload a single file to the presigned OSS URL.

    Notes:
        - The presigned URL is signed with NO Content-Type (MinerU's backend uses
          requests.put(url, data=f) which sends no Content-Type header).
        - aiohttp automatically sets Content-Type: application/octet-stream for
          bytes payloads, which breaks the OSS signature (403 SignatureDoesNotMatch).
        - skip_auto_headers suppresses the automatic header so no Content-Type is sent,
          matching the empty Content-Type used when the presigned URL was created.
        - Must NOT use chunked transfer; bytes payload sets a fixed Content-Length.
    """
    file_bytes = Path(file_path).read_bytes()
    async with session.put(
        url,
        data=file_bytes,
        skip_auto_headers={"Content-Type"},
    ) as resp:
        if resp.status == 200:
            logger.info(f"{TAG} uploaded: {os.path.basename(file_path)}")
        else:
            text = await resp.text()
            raise Exception(f"Upload failed ({resp.status}): {text}")


async def _poll(session: aiohttp.ClientSession, batch_id: str) -> List[dict]:
    """Poll task status until all items complete."""
    while True:
        async with session.get(
            f"{settings.MINERU_RESULT_URL}/{batch_id}", headers=settings.MINERU_HEADERS
        ) as resp:
            result = await resp.json()
            if result.get("code") != 0:
                logger.warning(f"{TAG} poll failed: {result}")
                await asyncio.sleep(settings.MINERU_POLL_INTERVAL)
                continue

            items = result["data"]["extract_result"]
            running = [i for i in items if i["state"] not in ("done", "failed")]
            for i in items:
                logger.info(f"{TAG} {i['file_name']}: {i['state']}")
            if not running:
                return items

        await asyncio.sleep(settings.MINERU_POLL_INTERVAL)


async def _download(session: aiohttp.ClientSession, items: List[dict], output_dir: str):
    """Download and extract completed results."""
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    for item in items:
        if item["state"] != "done":
            logger.warning(f"{TAG} skip {item['file_name']}: {item['state']}")
            continue

        name = Path(item["file_name"]).stem
        target = Path(output_dir) / name
        target.mkdir(parents=True, exist_ok=True)

        zip_url = item["full_zip_url"]
        logger.info(f"{TAG} downloading: {zip_url}")
        # Use a separate plain session (no auth headers) with a timeout.
        # CDN downloads can be slow; 300 s total socket read timeout.
        timeout = aiohttp.ClientTimeout(total=300)
        async with aiohttp.ClientSession(timeout=timeout) as cdn:
            async with cdn.get(zip_url) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise Exception(
                        f"Download failed ({resp.status}) for {item['file_name']}: {text[:200]}"
                    )
                data = io.BytesIO(await resp.read())

        with zipfile.ZipFile(data, "r") as zf:
            for member in zf.infolist():
                if member.is_dir():
                    continue
                path = target / member.filename
                path.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(member) as src, open(path, "wb") as dst:
                    dst.write(src.read())

        logger.info(f"{TAG} extracted: {name}")


async def process_files(file_paths: List[str], output_dir: Optional[str] = None) -> List[dict]:
    """Process PDF files through MinerU pipeline."""
    # Use absolute path so the route handler can find files regardless of CWD.
    out = output_dir or str(Path(settings.BASE_DIR) / settings.DOWNLOAD_DIR)
    async with aiohttp.ClientSession() as session:
        batch_id, urls = await _apply_urls(session, file_paths)
        for path, url in zip(file_paths, urls):
            await _upload(session, path, url)
        results = await _poll(session, batch_id)
        await _download(session, results, out)
        logger.info(f"{TAG} done")
        return results


def process_sync(file_paths: List[str], output_dir: Optional[str] = None) -> List[dict]:
    """Synchronous wrapper for process_files."""
    return asyncio.run(process_files(file_paths, output_dir))
