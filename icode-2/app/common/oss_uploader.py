# -*- coding: utf-8 -*-
import os
from typing import Callable, Optional

import oss2


def upload_file_to_oss(local_path: str, folder: str = "brain_analysis", logger: Optional[Callable[[str], None]] = None) -> Optional[str]:
    """将本地文件上传到阿里云 OSS，并返回可访问的分享链接。"""
    if logger is None:
        def logger(msg: str):
            print(msg)

    if not local_path or not os.path.exists(local_path):
        logger(f"上传失败：本地文件不存在：{local_path}")
        return None

    try:
        access_key_id = ''
        access_key_secret = ''
        endpoint = 'oss-cn-guangzhou.aliyuncs.com'
        bucket_name = ''

        auth = oss2.Auth(access_key_id, access_key_secret)
        bucket = oss2.Bucket(auth, endpoint, bucket_name)

        filename = os.path.basename(local_path)
        object_key = f"{folder}/{filename}"

        with open(local_path, 'rb') as f:
            result = bucket.put_object(object_key, f)

        if result.status == 200:
            share_url = f"https://{bucket_name}.{endpoint}/{object_key}"
            logger(f"文件已上传到 OSS：{share_url}")
            return share_url
        logger(f"OSS 上传失败，状态码：{result.status}")
        return None
    except Exception as exc:
        logger(f"OSS 上传异常：{exc}")
        return None
