# Copyright 2014 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"). You
# may not use this file except in compliance with the License. A copy of
# the License is located at
#
# http://aws.amazon.com/apache2.0/
#
# or in the "license" file accompanying this file. This file is
# distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF
# ANY KIND, either express or implied. See the License for the specific
# language governing permissions and limitations under the License.

import os
from io import BytesIO
import math
import sys
import threading

from cement.utils.misc import minimal_logger

from ebcli.lib import aws
from ebcli.objects.exceptions import (
    EndOfTestError,
    NotFoundError,
    FileTooLargeError,
    UploadError
)
from ebcli.core import fileoperations, io
from ebcli.lib.utils import static_var


LOG = minimal_logger(__name__)
CHUNK_SIZE = 5252880  # Minimum chunk size allowed by S3
THREAD_COUNT = 8  # Number of threads to use for multithreaded mode


def _make_api_call(operation_name, **operation_options):
    return aws.make_api_call('s3', operation_name, **operation_options)


def upload_file(bucket, key, file_path):
    with open(file_path, 'rb') as fp:
        return _make_api_call('put_object',
                              Bucket=bucket,
                              Key=key,
                              Body=fp)


def __raise_if_bucket_is_empty(result):
    if not result.get('Contents'):
        raise NotFoundError('Object not found.')


def elasticbeanstalk_bucket_for_account(account_id, region_name):
    LOG.debug('Inside create_bucket api wrapper')
    bucket_name = 'elasticbeanstalk-{region_name}-{account_id}'.format(
        region_name=region_name,
        account_id=account_id
    )

    if not bucket_exists(bucket_name):
        _make_api_call(
            'create_bucket',
            Bucket=bucket_name,
            CreateBucketConfiguration={
                'LocationConstraint': region_name
            },
        )

    return bucket_name


def bucket_exists(bucket):
    LOG.debug('Inside list_buckets api wrapper')
    return bucket in [
        bucket['Name']
        for bucket in _make_api_call('list_buckets')['Buckets']
    ]


def get_object_info(bucket, object_key):
    result = _make_api_call(
        'list_objects',
        Bucket=bucket,
        Prefix=object_key
    )

    __raise_if_bucket_is_empty(result)

    objects = result['Contents']
    if len(objects) == 1:
        return objects[0]
    else:
        s3_object = next((s3_object for s3_object in objects if s3_object['Key'] == object_key), None)

        if not s3_object:
            raise NotFoundError('Object not found.')

        return s3_object


def get_object(bucket, key):
    result = _make_api_call('get_object',
                            Bucket=bucket,
                            Key=key)
    return result['Body'].read()


def delete_objects(bucket, keys):
    objects = [dict(Key=k) for k in keys]
    result = _make_api_call('delete_objects',
                            Bucket=bucket,
                            Delete={'Objects': objects})
    return result


def upload_workspace_version(bucket, key, file_path, workspace_type='Application'):
    cwd = os.getcwd()
    try:
        fileoperations.ProjectRoot.traverse()
        size = os.path.getsize(file_path)
    except OSError as err:
        if err.errno == 2:
            raise NotFoundError(
                '{0} Version does not exist locally ({1}).'
                ' Try uploading the Application Version again.'.format(
                    workspace_type,
                    err.filename
                )
            )
        raise err
    finally:
        os.chdir(cwd)

    LOG.debug('Upload {0} Version. File size = {1}'.format(workspace_type, str(size)))
    if size > 536870912:
        raise FileTooLargeError('Archive cannot be any larger than 512MB')
    if size < 7340032:
        result = simple_upload(bucket, key, file_path)

    else:
        result = multithreaded_upload(bucket, key, file_path)
    return result


def upload_application_version(bucket, key, file_path):
    upload_workspace_version(bucket, key, file_path, 'Application')


def upload_platform_version(bucket, key, file_path):
    upload_workspace_version(bucket, key, file_path, 'Platform')


def simple_upload(bucket, key, file_path):
    io.echo('Uploading', key, 'to S3. This may take a while.')
    result = upload_file(bucket, key, file_path)
    io.echo('Upload Complete.')
    return result


def multithreaded_upload(bucket, key, file_path):
    """
    Upload a file in multiple parts using multiple threads.
    Takes advantage of S3's multipart upload.
    :param bucket: S3 bucket name
    :param key: keyname of file to be uploaded
    :param file_path: full path location of file to be uploaded
    :param region: region to use for S3
    :return: Result dictionary
    """

    size = os.path.getsize(file_path)
    total_parts = math.ceil(size / CHUNK_SIZE)  # Number of parts needed
    LOG.debug('Doing multi-threaded upload. Parts Needed=' + str(total_parts))

    upload_id = _get_multipart_upload_id(bucket, key)
    io.update_upload_progress(0)

    # Upload parts
    try:
        etaglist = []  # list for part id's (etags)
        with open(file_path, 'rb') as f:
            # Create threads to handle parts of upload
            lock = threading.Lock()
            jobs = []
            for i in range(THREAD_COUNT):
                p = threading.Thread(
                    target=_upload_chunk,
                    args=(f, lock, etaglist, total_parts,
                          bucket, key, upload_id),
                    )
                p.daemon = True
                jobs.append(p)
                p.start()

            _wait_for_threads(jobs)

        # S3 requires the etag list to be sorted
        etaglist = sorted(etaglist, key=lambda k: k['PartNumber'])

        if not _all_parts_were_uploaded(etaglist, total_parts):
            LOG.debug('Uploaded {0} parts, but should have uploaded {1} parts.'
                      .format(len(etaglist), total_parts))
            raise UploadError('An error occured while uploading Application Version. '
                              'Use the --debug option for more information if the problem persists.')
        result = _make_api_call(
            'complete_multipart_upload',
            Bucket=bucket,
            Key=key,
            UploadId=upload_id,
            MultipartUpload=dict(Parts=etaglist)
        )

        return result

    except (Exception, KeyboardInterrupt):
        # We dont want to clean up multipart in case a user decides to
        # continue later
        raise


def _all_parts_were_uploaded(etaglist, total_parts):
    return len(etaglist) == total_parts


def _wait_for_threads(jobs):
    alive = True
    while alive:
        alive = False
        for j in jobs:
            # We want to wait forever for the thread to finish.
            # j.join() however is a blocking call. We need to pass in a
            # time to j.join() so it is non blocking. This way a user can use
            # CTRL+C to terminate the command. 2**31 is the largest number we
            # can pass into j.join()
            if sys.version_info > (3, 0):
                timeout = threading.TIMEOUT_MAX
                j.join(timeout)
                if j.is_alive():
                    alive = True
            else:
                timeout = 2**16
                j.join(timeout)
                if j.isAlive():
                    alive = True


def _upload_chunk(f, lock, etaglist, total_parts, bucket, key, upload_id):
    LOG.debug('Creating child thread')
    while True:
        data, part = _read_next_section_from_file(f, lock)
        if not data:
            LOG.debug('No data left, closing')
            return
        # First check to see if s3 already has part
        for i in range(0, 5):
            try:
                etag = _get_part_etag(bucket, key, part, upload_id)
                if etag is None:
                    b = BytesIO()
                    b.write(data)
                    b.seek(0)
                    response = _make_api_call('upload_part',
                                              Bucket=bucket,
                                              Key=key,
                                              UploadId=upload_id,
                                              Body=b,
                                              PartNumber=part)
                    etag = response['ETag']

                etaglist.append({'PartNumber': part, 'ETag': etag})

                progress = (1/total_parts) * len(etaglist)
                io.update_upload_progress(progress)
                break
            except EndOfTestError:
                return
            except Exception as e:
                # We want to swallow all exceptions or else they will be
                # printed as a stack trace to the Console.
                # Exceptions are typically connections reset and
                # Various things.
                LOG.debug('Exception raised: ' + str(e))


def _get_part_etag(bucket, key, part, upload_id):
    try:
        response = _make_api_call(
            'list_parts',
            Bucket=bucket,
            Key=key,
            UploadId=upload_id
        )
    except Exception as e:
        # We want to swallow all exceptions or else they will be printed
        # as a stack trace to the Console
        LOG.debug('Exception raised: ' + str(e))
        return None

    if 'Parts' not in response:
        return None
    etag = next((i['ETag'] for i in response['Parts']
                 if i['PartNumber'] == part), None)
    return etag


def _get_multipart_upload_id(bucket, key):
    # Check to see if multipart already exists
    response = _make_api_call('list_multipart_uploads',
                              Bucket=bucket,
                              Prefix=key)

    try:
        for r in response['Uploads']:
            if r['Key'] == key:
                return r['UploadId']
    except KeyError:
        pass

    response = _make_api_call('create_multipart_upload',
                              Bucket=bucket,
                              Key=key)

    return response['UploadId']


@static_var('part_num', 0)
def _read_next_section_from_file(f, lock):
    try:
        with lock:
            data = f.read(CHUNK_SIZE)
            _read_next_section_from_file.part_num += 1
            return data, _read_next_section_from_file.part_num
    except ValueError as e:
        LOG.debug('Reading file raised error: ' + str(e))
        return '', None
