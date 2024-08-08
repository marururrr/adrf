from rest_framework.serializers import ModelSerializer as DRFModelSerializer

from adrf.serializers import ModelSerializer
from tests.models import SimpleUser


class SimpleUserDRFSerializer(DRFModelSerializer):
    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        model = SimpleUser
        fields = "__all__"


class SimpleUserSerializer(ModelSerializer):
    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        model = SimpleUser
        fields = "__all__"
