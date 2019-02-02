# third parties libraries
import tenacity

# whre all the bad requests are tried again...
# https://developers.google.com/drive/api/v3/handle-errors#exponential-backoff
MAX_ATTEMPTS = 30
EXP_MULTIPLIER = 0.5
EXP_MAX_WAIT = 60


# In what case should tenacity try again?
retry_exceptions = (
    # https://developers.google.com/drive/api/v3/handle-errors#403_user_rate_limit_exceeded
    tenacity.retry_if_exception_message(match=r".+?User Rate Limit Exceeded\.") |
    # https://developers.google.com/drive/api/v3/handle-errors#500_backend_error
    tenacity.retry_if_exception_message(match=r".+?Internal Error")
)


@tenacity.retry(stop=tenacity.stop_after_attempt(MAX_ATTEMPTS),
                wait=tenacity.wait_exponential(multiplier=EXP_MULTIPLIER, max=EXP_MAX_WAIT),
                retry=retry_exceptions)
def call_endpoint(endpoint, params):
    return endpoint(**params).execute()


@tenacity.retry(stop=tenacity.stop_after_attempt(MAX_ATTEMPTS),
                wait=tenacity.wait_exponential(multiplier=EXP_MULTIPLIER, max=EXP_MAX_WAIT),
                retry=retry_exceptions)
def execute_request(request):
    return request.execute()
