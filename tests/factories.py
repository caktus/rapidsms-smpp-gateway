import factory
import smpplib.consts

from django.utils.timezone import now
from factory.django import DjangoModelFactory
from faker import Faker
from rapidsms.models import Backend

from smpp_gateway.models import MOMessage, MTMessage, MTMessageStatus


class BackendFactory(DjangoModelFactory):
    class Meta:
        model = Backend

    name = factory.Sequence(lambda n: f"test_backend_{n}")


class MOMessageFactory(DjangoModelFactory):
    class Meta:
        model = MOMessage

    create_time = factory.LazyFunction(now)
    modify_time = factory.LazyFunction(now)
    backend = factory.SubFactory(BackendFactory)
    short_message = factory.LazyFunction(
        lambda: Faker().text(max_nb_chars=256).encode("ascii")
    )
    params = factory.Dict(
        {
            "destination_addr": "+46166371877",
            "source_addr": "+46166371876",
        }
    )
    status = MOMessage.Status.NEW


class MTMessageFactory(DjangoModelFactory):
    class Meta:
        model = MTMessage

    create_time = factory.LazyFunction(now)
    modify_time = factory.LazyFunction(now)
    backend = factory.SubFactory(BackendFactory)
    short_message = factory.Faker("sentence")
    params = {}
    status = MTMessage.Status.NEW


class MTMessageStatusFactory(DjangoModelFactory):
    class Meta:
        model = MTMessageStatus

    create_time = factory.LazyFunction(now)
    modify_time = factory.LazyFunction(now)
    mt_message = factory.SubFactory(MTMessageFactory)
    backend = factory.LazyAttribute(lambda o: o.mt_message.backend)
    sequence_number = factory.Sequence(lambda n: n + 1)
    command_status = smpplib.consts.SMPP_ESME_ROK
    message_id = ""
    delivery_report = b""
