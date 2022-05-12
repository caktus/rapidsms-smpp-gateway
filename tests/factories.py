import factory

from django.utils.timezone import now
from factory.django import DjangoModelFactory
from rapidsms.models import Backend

from smpp_gateway.models import MTMessage


class BackendFactory(DjangoModelFactory):
    class Meta:
        model = Backend

    name = factory.Sequence(lambda n: f"test_backend_{n}")


class MTMessageFactory(DjangoModelFactory):
    class Meta:
        model = MTMessage

    create_time = factory.LazyFunction(now)
    modify_time = factory.LazyFunction(now)
    backend = factory.SubFactory(BackendFactory)
    short_message = factory.Faker("sentence")
    params = {}
    status = MTMessage.Status.NEW