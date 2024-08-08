from collections import ChainMap
from typing import List

import pytest
from asgiref.sync import sync_to_async
from django.db import IntegrityError
from django.test import TestCase
from rest_framework import serializers
from rest_framework.test import APIRequestFactory

from adrf.serializers import (
    ModelSerializer,
    Serializer,
    serializer_adata,
    serializer_ais_valid,
    serializer_asave,
)
from tests.models import SimpleUser
from tests.serializers import SimpleUserDRFSerializer, SimpleUserSerializer

from .models import Additional, ContactList, Delivery, Order, User

factory = APIRequestFactory()


class TestFunctions(TestCase):
    async def test_serializer_adata_drf(self):
        serializer = SimpleUserDRFSerializer(
            data={"username": "test", "password": "pass", "age": 14}
        )
        assert await serializer_ais_valid(serializer)
        with pytest.warns(PendingDeprecationWarning, match="Pure DRF serializer?"):
            assert await serializer_adata(serializer) == {
                "username": "test",
                "password": "pass",
                "age": 14,
            }

    async def test_serializer_asave_drf(self):
        serializer = SimpleUserDRFSerializer(
            data={"username": "test", "password": "pass", "age": 14}
        )
        assert await serializer_ais_valid(serializer)
        assert not await SimpleUser.objects.filter(username="test").aexists()
        with pytest.warns(PendingDeprecationWarning, match="Pure DRF serializer?"):
            user = await serializer_asave(serializer)
            assert user is not None
            assert user.username == "test"
            assert user.password == "pass"
            assert user.age == 14
            assert await SimpleUser.objects.aget(username="test") == user

    async def test_serializer_adata_adrf(self):
        serializer = SimpleUserSerializer(
            data={"username": "test", "password": "pass", "age": 14}
        )
        assert await serializer_ais_valid(serializer)
        assert await serializer_adata(serializer) == {
            "username": "test",
            "password": "pass",
            "age": 14,
        }

    async def test_serializer_asave_adrf(self):
        serializer = SimpleUserSerializer(
            data={"username": "test", "password": "pass", "age": 14}
        )
        assert await serializer_ais_valid(serializer)
        assert not await SimpleUser.objects.filter(username="test").aexists()
        user = await serializer_asave(serializer)
        assert user is not None
        assert user.username == "test"
        assert user.password == "pass"
        assert user.age == 14
        assert await SimpleUser.objects.aget(username="test") == user


class MockObject:
    def __init__(self, **kwargs):
        self._kwargs = kwargs
        self.pk = kwargs.get("pk", None)

        for key, val in kwargs.items():
            setattr(self, key, val)


class TestSerializer(TestCase):
    def setUp(self):
        class SimpleSerializer(Serializer):
            username = serializers.CharField()
            password = serializers.CharField()
            age = serializers.IntegerField()

        class CrudSerializer(Serializer):
            username = serializers.CharField()
            password = serializers.CharField()
            age = serializers.IntegerField()

            async def acreate(self, validated_data):
                return MockObject(**validated_data)

            async def aupdate(self, instance, validated_data):
                return MockObject(**validated_data)

        self.simple_serializer = SimpleSerializer
        self.crud_serializer = CrudSerializer

        self.default_data = {
            "username": "test",
            "password": "test",
            "age": 25,
        }
        self.default_object = MockObject(**self.default_data)

    async def test_serializer_valid(self):
        data = {
            "username": "test",
            "password": "test",
            "age": 10,
        }
        serializer = self.simple_serializer(data=data)
        assert serializer.is_valid()
        assert await serializer.adata == data
        assert serializer.errors == {}

    async def test_serializer_invalid(self):
        data = {
            "username": "test",
            "password": "test",
        }
        serializer = self.simple_serializer(data=data)

        assert not serializer.is_valid()
        assert serializer.validated_data == {}
        assert await serializer.adata == data
        assert serializer.errors == {"age": ["This field is required."]}

    async def test_many_argument(self):
        data = [
            {
                "username": "test",
                "password": "test",
                "age": 10,
            }
        ]
        serializer = self.simple_serializer(data=data, many=True)

        assert serializer.is_valid()
        assert serializer.validated_data == data
        assert await serializer.adata == data

    async def test_many_argument_allow_empty_is_False(self):
        data = []
        serializer = self.simple_serializer(data=data, many=True, allow_empty=False)
        assert not serializer.is_valid()
        assert serializer.errors["non_field_errors"]
        assert serializer.errors["non_field_errors"][0].code == "empty"

    async def test_many_argument_max_length(self):
        data = [
            {
                "username": "test",
                "password": "test",
                "age": 10,
            },
            {
                "username": "test2",
                "password": "test2",
                "age": 11,
            },
        ]
        serializer = self.simple_serializer(data=data, many=True, max_length=1)
        assert not serializer.is_valid()
        assert serializer.errors["non_field_errors"]
        assert serializer.errors["non_field_errors"][0].code == "max_length"

    async def test_many_argument_min_length(self):
        data = [
            {
                "username": "test",
                "password": "test",
                "age": 10,
            }
        ]
        serializer = self.simple_serializer(data=data, many=True, min_length=2)
        assert not serializer.is_valid()
        assert serializer.errors["non_field_errors"]
        assert serializer.errors["non_field_errors"][0].code == "min_length"

    async def test_invalid_datatype(self):
        data = [
            {
                "username": "test",
                "password": "test",
                "age": 10,
            }
        ]
        serializer = self.simple_serializer(data=data)

        assert not serializer.is_valid()
        assert serializer.validated_data == {}
        assert await serializer.adata == {}

        assert serializer.errors == {
            "non_field_errors": ["Invalid data. Expected a dictionary, but got list."]
        }

    async def test_partial_validation(self):
        data = {
            "username": "test",
            "password": "test",
        }
        serializer = self.simple_serializer(data=data, partial=True)

        assert serializer.is_valid()
        assert serializer.validated_data == data
        assert serializer.errors == {}

    async def test_not_validated(self):
        data = {
            "username": "test",
            "password": "test",
            "age": 10,
        }
        serializer = self.simple_serializer(data=data)

        with pytest.raises(
            AssertionError,
            match="When a serializer is passed a `data` keyword argument you",
        ):
            _ = await serializer.adata

    async def test_serialize_chainmap(self):
        data = {"username": "test"}, {"password": "test"}, {"age": 10}

        serializer = self.simple_serializer(data=ChainMap(*data))

        assert serializer.is_valid()
        assert serializer.validated_data == {
            "username": "test",
            "password": "test",
            "age": 10,
        }
        assert serializer.errors == {}

    async def test_crud_serializer_create(self):
        # Create a valid data payload
        data = self.default_data

        # Create an instance of the serializer
        serializer = self.crud_serializer(data=data)

        assert serializer.is_valid()

        # Create the object
        created_object = await serializer.acreate(serializer.validated_data)

        # Verify the object has been created successfully
        assert isinstance(created_object, MockObject)

        # Verify the object has the correct data
        assert created_object.username == data["username"]
        assert created_object.password == data["password"]
        assert created_object.age == data["age"]

    async def test_crud_serializer_update(self):
        # Create a valid data payload
        default_object = self.default_object
        data = {
            "username": "test2",
            "password": "test2",
            "age": 30,
        }

        # Update the object using the serializer
        serializer = self.crud_serializer(default_object, data=data)

        assert serializer.is_valid()

        # Update the object
        updated_object = await serializer.aupdate(
            default_object, serializer.validated_data
        )

        # Verify the object has been updated successfully
        assert isinstance(updated_object, MockObject)
        assert updated_object.username == data["username"]
        assert updated_object.password == data["password"]
        assert updated_object.age == data["age"]

    # test asave
    async def test_crud_serializer_save(self):
        # Create a valid data payload
        data = self.default_data

        # Create an instance of the serializer
        serializer = self.crud_serializer(data=data)

        assert serializer.is_valid()

        # Create the object
        created_object = await serializer.asave()

        # Verify the object has been created successfully
        assert isinstance(created_object, MockObject)

        # Verify the object has the correct data
        assert created_object.username == data["username"]
        assert created_object.password == data["password"]
        assert created_object.age == data["age"]

    async def test_crud_serializer_to_representation(self):
        # Create a valid data payload
        default_object = self.default_object

        # Update the object using the serializer
        serializer = self.crud_serializer(default_object)

        # Update the object
        representation = await serializer.ato_representation(default_object)

        # Verify the object has been updated successfully
        assert isinstance(representation, dict)
        assert representation["username"] == default_object.username
        assert representation["password"] == default_object.password
        assert representation["age"] == default_object.age

    # test that normal non-async serializers work
    def test_sync_serializer_valid(self):
        data = {
            "username": "test",
            "password": "test",
            "age": 10,
        }
        serializer = self.simple_serializer(data=data)
        assert serializer.is_valid()
        assert serializer.data == data
        assert serializer.errors == {}


class TestModelSerializer(TestCase):
    def setUp(self) -> None:
        class UserSerializer(ModelSerializer):
            class Meta:
                model = User
                fields = ("username",)

        class OrderSerializer(ModelSerializer):
            class Meta:
                model = Order
                fields = ("id", "user", "name")

        self.user_serializer = UserSerializer
        self.order_serializer = OrderSerializer

    async def test_user_serializer_valid(self):
        data = {
            "username": "test",
        }
        serializer = self.user_serializer(data=data)
        assert await sync_to_async(serializer.is_valid)()
        assert await serializer.adata == data
        assert serializer.errors == {}

    async def test_user_serializer_many(self):
        data = [
            {
                "username": "test",
            },
            {
                "username": "test2",
            },
        ]
        serializer = self.user_serializer(data=data, many=True)
        assert await serializer_ais_valid(serializer)
        ulist = await serializer_asave(serializer)
        assert ulist == [
            await User.objects.aget(username=data[0]["username"]),
            await User.objects.aget(username=data[1]["username"]),
        ]

    async def test_order_serializer_valid(self):
        user = await User.objects.acreate(username="test")
        data = {"user": user.id, "name": "Test order"}
        serializer = self.order_serializer(data=data)
        assert await sync_to_async(serializer.is_valid)()
        assert await serializer.adata == data
        assert serializer.errors == {}

    async def test_order_serializer_by_fresh_instance(self):
        user = await User.objects.acreate(username="test")
        order = await Order.objects.acreate(user=user, name="Test order")
        data = {"id": order.pk, "user": user.pk, "name": "Test order"}
        order_from_db = await Order.objects.aget(pk=order.pk)
        serializer = self.order_serializer(instance=order_from_db)
        assert await serializer.adata == data

    async def test_order_serializer_update(self):
        user = await User.objects.acreate(username="test")
        order = await Order.objects.acreate(user=user, name="Test order")
        order_from_db = await Order.objects.aget(pk=order.pk)
        data = {"name": "Test order(canceled)"}
        serializer = self.order_serializer(
            instance=order_from_db, data=data, partial=True
        )
        assert await serializer_ais_valid(serializer)
        mod_order = await serializer_asave(serializer)
        assert mod_order.pk == order_from_db.pk
        assert mod_order.name == "Test order(canceled)"


class TestModelSerializerWithForeignKeyField(TestCase):
    def setUp(self) -> None:
        class OrderSerializer(ModelSerializer):
            class Meta:
                model = Order
                fields = "__all__"

        # This requires a router?
        # class OrderHyperlinkedUserSerializer(ModelSerializer):
        #     user = serializers.HyperlinkedRelatedField(read_only=True)

        #     class Meta:
        #         model = Order
        #         fields = ("id", "user", "name")

        class DeliveryStringUserSerializer(ModelSerializer):
            order = serializers.StringRelatedField()

            class Meta:
                model = Delivery
                fields = ("id", "order", "deliverer")

        class DeliverySlugUserSerializer(ModelSerializer):
            deliverer = serializers.SlugRelatedField(
                slug_field="username", read_only=True
            )

            class Meta:
                model = Delivery
                fields = ("id", "order", "deliverer")

        class DeliveryInlineOrderSerializer(ModelSerializer):
            order = OrderSerializer()

            class Meta:
                model = Delivery
                fields = ("id", "order", "deliverer")

        self.string_serializer = DeliveryStringUserSerializer
        self.slug_serializer = DeliverySlugUserSerializer
        self.inline_serializer = DeliveryInlineOrderSerializer

    async def test_delivery_serializer_string_by_instance(self):
        user = await User.objects.acreate(username="test")
        order = await Order.objects.acreate(user=user, name="Test order")
        deliverer = await User.objects.acreate(username="runner")
        delivery = await Delivery.objects.acreate(order=order, deliverer=deliverer)
        serializer = self.string_serializer(instance=delivery)
        data = {
            "id": order.pk,
            "order": "Order<Test order by test>",
            "deliverer": deliverer.pk,
        }
        assert await serializer.adata == data

    async def test_delivery_serializer_string_by_fresh_instance(self):
        user = await User.objects.acreate(username="test")
        order = await Order.objects.acreate(user=user, name="Test order")
        deliverer = await User.objects.acreate(username="runner")
        delivery = await Delivery.objects.acreate(order=order, deliverer=deliverer)
        data = {
            "id": order.pk,
            "order": "Order<Test order by test>",
            "deliverer": deliverer.pk,
        }
        delivery_from_db = await Delivery.objects.aget(pk=delivery.pk)
        serializer = self.string_serializer(instance=delivery_from_db)
        assert await serializer.adata == data

    async def test_delivery_serializer_slug_by_instance(self):
        user = await User.objects.acreate(username="test")
        order = await Order.objects.acreate(user=user, name="Test order")
        deliverer = await User.objects.acreate(username="runner")
        delivery = await Delivery.objects.acreate(order=order, deliverer=deliverer)
        data = {
            "id": delivery.pk,
            "order": order.pk,
            "deliverer": "runner",
        }
        serializer = self.slug_serializer(instance=delivery)
        assert await serializer.adata == data

    async def test_delivery_serializer_slug_by_fresh_instance(self):
        user = await User.objects.acreate(username="test")
        order = await Order.objects.acreate(user=user, name="Test order")
        deliverer = await User.objects.acreate(username="runner")
        delivery = await Delivery.objects.acreate(order=order, deliverer=deliverer)
        data = {
            "id": delivery.pk,
            "order": order.pk,
            "deliverer": "runner",
        }
        delivery_from_db = await Delivery.objects.aget(pk=delivery.pk)
        serializer = self.slug_serializer(instance=delivery_from_db)
        assert await serializer.adata == data

    async def test_delivery_serializer_inline_by_instance(self):
        user = await User.objects.acreate(username="test")
        order = await Order.objects.acreate(user=user, name="Test order")
        deliverer = await User.objects.acreate(username="runner")
        delivery = await Delivery.objects.acreate(order=order, deliverer=deliverer)
        data = {
            "id": delivery.pk,
            "order": {"id": order.pk, "user": user.pk, "name": "Test order"},
            "deliverer": deliverer.pk,
        }
        serializer = self.inline_serializer(instance=delivery)
        assert await serializer.adata == data

    async def test_delivery_serializer_inline_by_fresh_instance(self):
        user = await User.objects.acreate(username="test")
        order = await Order.objects.acreate(user=user, name="Test order")
        deliverer = await User.objects.acreate(username="runner")
        delivery = await Delivery.objects.acreate(order=order, deliverer=deliverer)
        delivery_from_db = await Delivery.objects.aget(pk=delivery.pk)
        assert delivery_from_db.pk == delivery.pk
        serializer = self.inline_serializer(instance=delivery_from_db)
        data = {
            "id": delivery.pk,
            "order": {"id": order.pk, "user": user.pk, "name": "Test order"},
            "deliverer": deliverer.pk,
        }
        assert await serializer.adata == data

    async def test_delivery_serializer_inline_by_fresh_instance_with_deferred_fields(
        self,
    ):
        user = await User.objects.acreate(username="test")
        order = await Order.objects.acreate(user=user, name="Test order")
        deliverer = await User.objects.acreate(username="runner")
        delivery = await Delivery.objects.acreate(order=order, deliverer=deliverer)
        data = {
            "id": delivery.pk,
            "order": {"id": order.pk, "user": user.pk, "name": "Test order"},
            "deliverer": deliverer.pk,
        }
        delivery_from_db = await Delivery.objects.defer("order", "deliverer").aget(
            pk=delivery.pk
        )
        serializer = self.inline_serializer(instance=delivery_from_db)
        assert await serializer.adata == data

    async def test_delivery_serializer_inline_by_fresh_instance_with_order_None(
        self,
    ):
        deliverer = await User.objects.acreate(username="runner")
        delivery = await Delivery.objects.acreate(order=None, deliverer=deliverer)
        delivery_from_db = await Delivery.objects.aget(pk=delivery.pk)
        serializer = self.inline_serializer(instance=delivery_from_db)
        assert await serializer.adata == {
            "id": delivery.pk,
            "order": None,
            "deliverer": deliverer.pk,
        }

    async def test_delivery_serializer_inline_by_fresh_instance_with_vanished_order(
        self,
    ):
        user = await User.objects.acreate(username="test")
        order = await Order.objects.acreate(user=user, name="Test order")
        deliverer = await User.objects.acreate(username="runner")
        delivery = await Delivery.objects.acreate(order=order, deliverer=deliverer)
        delivery_from_db = await Delivery.objects.aget(pk=delivery.pk)
        serializer = self.inline_serializer(instance=delivery_from_db)
        await order.adelete()
        with pytest.raises(IntegrityError, match="Delivery lost order."):
            await serializer.adata
        # Needs to fix the integrity problem of vanished 'order' before cleaning up.
        delivery.order = None
        await delivery.asave()

    async def test_delivery_serializer_inline_by_fresh_instance_with_order_None_integrity_hack(
        self,
    ):
        deliverer = await User.objects.acreate(username="runner")
        delivery = await Delivery.objects.acreate(order=None, deliverer=deliverer)
        delivery_from_db = await Delivery.objects.aget(pk=delivery.pk)
        serializer = self.inline_serializer(instance=delivery_from_db)
        descriptor = getattr(delivery_from_db.__class__, "order")
        descriptor.field.null = False
        with pytest.raises(IntegrityError, match="Delivery has no order."):
            _ = await serializer.adata
        descriptor.field.null = True


class TestModelSerializerWithReverseRelatedField(TestCase):
    def setUp(self) -> None:
        class DelivererSerializer(ModelSerializer):
            class Meta:
                model = User
                fields = ("username", "delivery_set")

        self.deliverer_serializer = DelivererSerializer

    async def test_deliverer_serializer_empty(self):
        deliverer = await User.objects.acreate(username="runner")
        serializer = self.deliverer_serializer(instance=deliverer)
        data = {"username": "runner", "delivery_set": []}
        assert await serializer.adata == data

    async def test_deliverer_serializer_empty_by_fresh_instance(self):
        deliverer = await User.objects.acreate(username="runner")
        deliverer_from_db = await User.objects.aget(pk=deliverer.pk)
        serializer = self.deliverer_serializer(instance=deliverer_from_db)
        data = {"username": "runner", "delivery_set": []}
        assert await serializer.adata == data

    async def test_deliverer_serializer(self):
        deliverer = await User.objects.acreate(username="runner")
        deliveries = []
        for num in range(10):
            customer = await User.objects.acreate(username=f"customer{num}")
            order = await Order.objects.acreate(name=f"Order{num}", user=customer)
            deliveries.append(
                await Delivery.objects.acreate(order=order, deliverer=deliverer)
            )
        serializer = self.deliverer_serializer(instance=deliverer)
        adata = await serializer.adata
        assert adata["username"] == "runner"
        delivery_set = adata["delivery_set"]
        assert len(delivery_set) == 10
        for delivery in deliveries:
            assert delivery.pk in delivery_set

    async def test_deliverer_serializer_by_fresh_instance(self):
        deliverer = await User.objects.acreate(username="runner")
        deliveries = []
        for num in range(10):
            customer = await User.objects.acreate(username=f"customer{num}")
            order = await Order.objects.acreate(name=f"Order{num}", user=customer)
            deliveries.append(
                await Delivery.objects.acreate(order=order, deliverer=deliverer)
            )
        deliverer_from_db = await User.objects.aget(pk=deliverer.pk)
        serializer = self.deliverer_serializer(instance=deliverer_from_db)
        adata = await serializer.adata
        assert adata["username"] == "runner"
        delivery_set = adata["delivery_set"]
        assert len(delivery_set) == 10
        for delivery in deliveries:
            assert delivery.pk in delivery_set


class TestModelSerializerWithOneToOneField(TestCase):
    def setUp(self) -> None:
        class AdditionalSerializer(ModelSerializer):
            class Meta:
                model = Additional
                fields = "__all__"

        class ExtendedUserSerializer(ModelSerializer):
            additional = AdditionalSerializer()

            class Meta:
                model = User
                fields = ("id", "username", "additional")

        self.additional_serializer = AdditionalSerializer
        self.extended_user_serializer = ExtendedUserSerializer

    async def test_adittional_serializer(self):
        user = await User.objects.acreate(username="test")
        additional = await Additional.objects.acreate(user=user, nickname="Mr.T")
        data = {"user": user.pk, "nickname": "Mr.T"}
        serializer = self.additional_serializer(instance=additional)
        assert await serializer.adata == data

    async def test_extended_user_serializer(self):
        user = await User.objects.acreate(username="test")
        additional = await Additional.objects.acreate(user=user, nickname="Mr.T")
        data = {
            "id": user.pk,
            "username": "test",
            "additional": {"user": user.pk, "nickname": "Mr.T"},
        }
        serializer = self.extended_user_serializer(instance=user)
        assert await serializer.adata == data

    async def test_extended_user_serializer_by_fresh_instance(self):
        user = await User.objects.acreate(username="test")
        additional = await Additional.objects.acreate(user=user, nickname="Mr.T")
        data = {
            "id": user.pk,
            "username": "test",
            "additional": {"user": user.pk, "nickname": "Mr.T"},
        }
        user_from_db = await User.objects.aget(pk=user.pk)
        serializer = self.extended_user_serializer(instance=user_from_db)
        assert await serializer.adata == data

    async def test_extended_user_serializer_with_no_adittional(self):
        user = await User.objects.acreate(username="test")
        serializer = self.extended_user_serializer(instance=user)
        with pytest.raises(Exception, match="User has no additional."):
            await serializer.adata

    async def test_extended_user_serializer_with_uncommited_user(self):
        user = User(username="test")
        serializer = self.extended_user_serializer(instance=user)
        with pytest.raises(Exception, match="User has no additional."):
            await serializer.adata


class TestModelSerializerWithManyToManyField(TestCase):
    def setUp(self):
        class ContactListSerializer(ModelSerializer):
            class Meta:
                model = ContactList
                fields = "__all__"

        self.contact_list_serializer = ContactListSerializer

    async def test_serializer_with_m2m_relation(self):
        owner = await User.objects.acreate(username="owner")
        contacts = await ContactList.objects.acreate(user=owner)
        ulist: List[User] = []
        for num in range(10):
            u = await User.objects.acreate(username=f"friend{num}")
            ulist.append(u)
            await contacts.contacts.aadd(u)
        serializer = self.contact_list_serializer(instance=contacts)
        data = await serializer.adata
        assert data["user"] == owner.pk
        assert len(data["contacts"]) == len(ulist)
        for u in ulist:
            assert u.pk in data["contacts"]

    async def test_serializer_with_m2m_relation_by_fresh_instance(self):
        owner = await User.objects.acreate(username="owner")
        contacts = await ContactList.objects.acreate(user=owner)
        ulist: List[User] = []
        for num in range(10):
            u = await User.objects.acreate(username=f"friend{num}")
            ulist.append(u)
            await contacts.contacts.aadd(u)

        contacts_from_db = await ContactList.objects.aget(pk=contacts.pk)
        serializer = self.contact_list_serializer(instance=contacts_from_db)
        data = await serializer.adata
        assert data["user"] == owner.pk
        assert len(data["contacts"]) == len(ulist)
        for u in ulist:
            assert u.pk in data["contacts"]

    async def test_serializer_with_m2m_relation_by_data(self):
        owner = await User.objects.acreate(username="owner")
        ulist: List[User] = []
        for num in range(10):
            u = await User.objects.acreate(username=f"friend{num}")
            ulist.append(u)
        serializer = self.contact_list_serializer(
            data={"user": owner.pk, "contacts": [u.pk for u in ulist]}
        )
        assert await serializer_ais_valid(serializer)
        contacts = await serializer_asave(serializer)
        assert contacts.user == owner
        async for u in contacts.contacts.all():
            assert u in ulist

    async def test_serializer_with_m2m_relation_update_by_data(self):
        owner = await User.objects.acreate(username="owner")
        contacts = await ContactList.objects.acreate(user=owner)
        ulist: List[User] = []
        for num in range(10):
            u = await User.objects.acreate(username=f"friend{num}")
            ulist.append(u)
            await contacts.contacts.aadd(u)

        ulist.append(await User.objects.acreate(username="partner"))
        contacts_from_db = await ContactList.objects.aget(pk=contacts.pk)
        serializer = self.contact_list_serializer(
            instance=contacts_from_db,
            data={"user": owner.pk, "contacts": [u.pk for u in ulist]},
        )
        assert await serializer_ais_valid(serializer)
        updated = await serializer_asave(serializer)
        assert updated.user == owner
        async for u in updated.contacts.all():
            assert u in ulist
