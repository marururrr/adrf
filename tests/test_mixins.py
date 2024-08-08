import json
import warnings
from typing import Any

import pytest
from django.db.models import Model
from django.test import TestCase
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.request import Request
from rest_framework.serializers import BaseSerializer as DRFBaseSerializer
from rest_framework.test import APIRequestFactory

from adrf.generics import GenericAPIView
from adrf.mixins import (
    CreateModelMixin,
    DestroyModelMixin,
    ListModelMixin,
    RetrieveModelMixin,
    UpdateModelMixin,
)
from adrf.serializers import serializer_ais_valid
from adrf.test import assume_async_view
from tests.models import SimpleUser
from tests.serializers import SimpleUserSerializer

factory = APIRequestFactory()


class BaseAsyncSimpleUserView(GenericAPIView):
    queryset = SimpleUser.objects.order_by("pk")
    serializer_class = SimpleUserSerializer


class TestCreateModelMixin(TestCase):
    def setUp(self):
        class AsyncSimpleUserView(CreateModelMixin, BaseAsyncSimpleUserView):
            async def post(self, request: Request, *args: Any, **kwargs: Any):
                return await self.create(request, *args, **kwargs)

        class AsyncSimpleUserViewHybrid(AsyncSimpleUserView):
            """Test case having sync implementation of perform_create()"""

            def perform_create(self, serializer: DRFBaseSerializer):  # type: ignore
                serializer.save()

        class AsyncSimpleUserViewHybridNoWarn(AsyncSimpleUserViewHybrid):
            """Test case having sync implementation of perform_create()"""

            use_sync_perform_create = True

        self.simple_user_view = AsyncSimpleUserView
        self.simple_user_view_hybrid = AsyncSimpleUserViewHybrid
        self.simple_user_view_hybrid_no_warn = AsyncSimpleUserViewHybridNoWarn

    async def test_create(self):
        request = factory.post("/", {"username": "test", "password": "pass", "age": 14})
        assert not await SimpleUser.objects.filter(username="test").aexists()

        view = self.simple_user_view.as_view()
        response = await assume_async_view(view)(request)
        assert response.status_code == status.HTTP_201_CREATED
        data: dict[str, Any] = response.data  # type: ignore
        user = await SimpleUser.objects.aget(username="test")
        assert user.pk == data["id"]
        assert user.username == data["username"]
        assert user.password == data["password"]
        assert user.age == data["age"]

    async def test_create_hybrid_warn(self):
        request = factory.post("/", {"username": "test", "password": "pass", "age": 14})

        assert not await SimpleUser.objects.filter(username="test").aexists()
        view = self.simple_user_view_hybrid.as_view()
        with pytest.warns(
            PendingDeprecationWarning, match="Non async perform_create()?"
        ):
            response = await assume_async_view(view)(request)
            assert response.status_code == status.HTTP_201_CREATED
            data: dict[str, Any] = response.data  # type: ignore
            user = await SimpleUser.objects.aget(username="test")
            assert user.pk == data["id"]
            assert user.username == data["username"]
            assert user.password == data["password"]
            assert user.age == data["age"]

    async def test_create_hybrid_no_warn(self):
        request = factory.post("/", {"username": "test", "password": "pass", "age": 14})

        assert not await SimpleUser.objects.filter(username="test").aexists()
        view = self.simple_user_view_hybrid_no_warn.as_view()
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("ignore")
            response = await assume_async_view(view)(request)
            assert len(w) == 0

        assert response.status_code == status.HTTP_201_CREATED
        data: dict[str, Any] = response.data  # type: ignore
        user = await SimpleUser.objects.aget(username="test")
        assert user.pk == data["id"]
        assert user.username == data["username"]
        assert user.password == data["password"]
        assert user.age == data["age"]

    async def test_perform_create(self):
        view = self.simple_user_view()
        request = view.initialize_request(
            factory.post("/", {"username": "test", "password": "pass", "age": 14})
        )

        serializer = SimpleUserSerializer(data=request.data)
        assert await serializer_ais_valid(serializer)

        assert not await SimpleUser.objects.filter(username="test").aexists()
        await view.perform_create(serializer)
        user = await SimpleUser.objects.aget(username="test")
        assert user.username == "test"
        assert user.password == "pass"
        assert user.age == 14

    # async def test_get_success_headers(self):
    #     pass


class TestListModelMixin(TestCase):
    def setUp(self):
        class CustomPageNumberPagination(PageNumberPagination):
            page_query_param = "page"
            page_size_query_param = "page_size"
            max_page_size = 50

        class AsyncSimpleUserView(ListModelMixin, BaseAsyncSimpleUserView):
            pagination_class = CustomPageNumberPagination

            async def get(self, request: Request, *args: Any, **kwargs: Any):
                return await self.list(request, *args, **kwargs)

        self.simple_user_view = AsyncSimpleUserView()

    async def test_empty_list(self):
        request = factory.get("/")
        assert await SimpleUser.objects.acount() == 0
        view = self.simple_user_view.as_view()
        response = await assume_async_view(view)(request)
        response.render()
        assert json.loads(response.content) == []

    async def test_list(self):
        u1 = await SimpleUser.objects.acreate(
            username="user1", password="pass1", age=14
        )
        u2 = await SimpleUser.objects.acreate(
            username="user2", password="pass2", age=74
        )
        assert await SimpleUser.objects.acount() == 2

        request = factory.get("/")
        view = self.simple_user_view.as_view()
        response = await assume_async_view(view)(request)
        response.render()
        assert json.loads(response.content) == [
            {
                "id": u1.pk,
                "username": u1.username,
                "password": u1.password,
                "age": u1.age,
            },
            {
                "id": u2.pk,
                "username": u2.username,
                "password": u2.password,
                "age": u2.age,
            },
        ]

    async def test_list_paginated(self):
        users: list[SimpleUser] = []
        for count in range(15):
            users.append(
                await SimpleUser.objects.acreate(
                    username="user%s" % count, password="pass%s" % count, age=14 + count
                )
            )
        page_size = 5

        request = factory.get(f"/?page=1&page_size={page_size}")
        view = self.simple_user_view.as_view()
        response = await assume_async_view(view)(request)
        response.render()
        data = json.loads(response.content)
        assert data["count"] == len(users)
        users_list = data["results"]
        assert len(users_list) == page_size
        for idx in range(page_size):
            assert users_list[idx] == {
                "id": users[idx].pk,
                "username": users[idx].username,
                "password": users[idx].password,
                "age": users[idx].age,
            }


class TestRetrieveModelMixin(TestCase):
    def setUp(self):
        class AsyncSimpleUserView(RetrieveModelMixin, BaseAsyncSimpleUserView):
            async def get(self, request: Request, *args: Any, **kwargs: Any):
                return await self.retrieve(request, *args, **kwargs)

        self.simple_user_view = AsyncSimpleUserView()

    async def test_retrieve(self):
        user = await SimpleUser.objects.acreate(
            username="test", password="pass", age=88
        )
        request = factory.get(f"/{user.pk}")
        view = self.simple_user_view.as_view()
        response = await assume_async_view(view)(request, pk=user.pk)
        response.render()
        data = json.loads(response.content)
        assert data == {
            "id": user.pk,
            "username": user.username,
            "password": user.password,
            "age": user.age,
        }

    async def test_retrieve_404(self):
        assert await SimpleUser.objects.acount() == 0
        request = factory.get("/666")
        view = self.simple_user_view.as_view()
        response = await assume_async_view(view)(request, pk=666)
        response.render()
        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = json.loads(response.content)
        assert data == {"detail": "No SimpleUser matches the given query."}


class TestUpdateModelMixin(TestCase):
    def setUp(self):
        class AsyncSimpleUserView(UpdateModelMixin, BaseAsyncSimpleUserView):
            async def put(self, request: Request, *args: Any, **kwargs: Any):
                return await self.update(request, *args, **kwargs)

            async def patch(self, request: Request, *args: Any, **kwargs: Any):
                return await self.partial_update(request, *args, **kwargs)

        class AsyncSimpleUserViewHybrid(AsyncSimpleUserView):
            """Test case having sync implementation of perform_update()"""

            def perform_update(self, serializer: DRFBaseSerializer):  # type: ignore
                serializer.save()

        class AsyncSimpleUserViewHybridNoWarn(AsyncSimpleUserViewHybrid):
            """Test case having sync implementation of perform_update()"""

            use_sync_perform_update = True

        self.simple_user_view = AsyncSimpleUserView
        self.simple_user_view_hybrid = AsyncSimpleUserViewHybrid
        self.simple_user_view_hybrid_no_warn = AsyncSimpleUserViewHybridNoWarn

    async def test_update(self):
        user = await SimpleUser.objects.acreate(
            username="test", password="pass", age=14
        )
        request = factory.put(
            f"/{user.pk}", {"username": "test", "password": "word", "age": 16}
        )

        view = self.simple_user_view.as_view()
        response = await assume_async_view(view)(request, pk=user.pk)
        assert response.status_code == status.HTTP_200_OK
        data: dict[str, Any] = response.data  # type: ignore
        user = await SimpleUser.objects.aget(pk=user.pk)
        assert user.pk == data["id"]
        assert user.username == data["username"]
        assert user.username == "test"
        assert user.password == data["password"]
        assert user.password == "word"
        assert user.age == data["age"]
        assert user.age == 16

    async def test_update_hybrid_warn(self):
        user = await SimpleUser.objects.acreate(
            username="test", password="pass", age=14
        )
        request = factory.put(
            f"/{user.pk}", {"username": "test", "password": "word", "age": 16}
        )

        view = self.simple_user_view_hybrid.as_view()
        with pytest.warns(
            PendingDeprecationWarning, match="Non async perform_update()?"
        ):
            response = await assume_async_view(view)(request, pk=user.pk)
            assert response.status_code == status.HTTP_200_OK
            data: dict[str, Any] = response.data  # type: ignore
            user = await SimpleUser.objects.aget(pk=user.pk)
            assert user.pk == data["id"]
            assert user.username == data["username"]
            assert user.username == "test"
            assert user.password == data["password"]
            assert user.password == "word"
            assert user.age == data["age"]
            assert user.age == 16

    async def test_update_hybrid_no_warn(self):
        user = await SimpleUser.objects.acreate(
            username="test", password="pass", age=14
        )
        request = factory.put(
            f"/{user.pk}", {"username": "test", "password": "word", "age": 16}
        )

        view = self.simple_user_view_hybrid_no_warn.as_view()
        with warnings.catch_warnings(record=True) as w:
            response = await assume_async_view(view)(request, pk=user.pk)
            assert len(w) == 0
        assert response.status_code == status.HTTP_200_OK
        data: dict[str, Any] = response.data  # type: ignore
        user = await SimpleUser.objects.aget(pk=user.pk)
        assert user.pk == data["id"]
        assert user.username == data["username"]
        assert user.username == "test"
        assert user.password == data["password"]
        assert user.password == "word"
        assert user.age == data["age"]
        assert user.age == 16

    async def test_partial_update(self):
        user = await SimpleUser.objects.acreate(
            username="test", password="pass", age=14
        )
        request = factory.patch(f"/{user.pk}", {"age": 16})

        view = self.simple_user_view.as_view()
        response = await assume_async_view(view)(request, pk=user.pk)
        assert response.status_code == status.HTTP_200_OK
        data: dict[str, Any] = response.data  # type: ignore
        user = await SimpleUser.objects.aget(pk=user.pk)
        assert user.pk == data["id"]
        assert user.username == data["username"]
        assert user.username == "test"
        assert user.password == data["password"]
        assert user.password == "pass"
        assert user.age == data["age"]
        assert user.age == 16

    async def test_partial_update_hybrid_warn(self):
        user = await SimpleUser.objects.acreate(
            username="test", password="pass", age=14
        )
        request = factory.patch(f"/{user.pk}", {"age": 16})

        view = self.simple_user_view_hybrid.as_view()
        with pytest.warns(
            PendingDeprecationWarning, match="Non async perform_update()?"
        ):
            response = await assume_async_view(view)(request, pk=user.pk)
            assert response.status_code == status.HTTP_200_OK
            data: dict[str, Any] = response.data  # type: ignore
            user = await SimpleUser.objects.aget(pk=user.pk)
            assert user.pk == data["id"]
            assert user.username == data["username"]
            assert user.username == "test"
            assert user.password == data["password"]
            assert user.password == "pass"
            assert user.age == data["age"]
            assert user.age == 16

    async def test_partial_update_hybrid_no_warn(self):
        user = await SimpleUser.objects.acreate(
            username="test", password="pass", age=14
        )
        request = factory.patch(f"/{user.pk}", {"age": 16})

        view = self.simple_user_view_hybrid_no_warn.as_view()
        with warnings.catch_warnings(record=True) as w:
            response = await assume_async_view(view)(request, pk=user.pk)
            assert len(w) == 0
        assert response.status_code == status.HTTP_200_OK
        data: dict[str, Any] = response.data  # type: ignore
        user = await SimpleUser.objects.aget(pk=user.pk)
        assert user.pk == data["id"]
        assert user.username == data["username"]
        assert user.username == "test"
        assert user.password == data["password"]
        assert user.password == "pass"
        assert user.age == data["age"]
        assert user.age == 16


class TestDestroyModelMixin(TestCase):
    def setUp(self):
        class AsyncSimpleUserView(DestroyModelMixin, BaseAsyncSimpleUserView):
            async def delete(self, request: Request, *args: Any, **kwargs: Any):
                return await self.destroy(request, *args, **kwargs)

        class AsyncSimpleUserViewHybrid(AsyncSimpleUserView):
            """Test case having sync implementation of perform_create()"""

            def perform_destroy(self, instance: Model):  # type: ignore
                instance.delete()

        class AsyncSimpleUserViewHybridNoWarn(AsyncSimpleUserViewHybrid):
            """Test case having sync implementation of perform_create()"""

            use_sync_perform_destroy = True

        self.simple_user_view = AsyncSimpleUserView
        self.simple_user_view_hybrid = AsyncSimpleUserViewHybrid
        self.simple_user_view_hybrid_no_warn = AsyncSimpleUserViewHybridNoWarn

    async def test_destroy(self):
        user = await SimpleUser.objects.acreate(
            username="test", password="pass", age=88
        )
        request = factory.delete(f"/{user.pk}")
        view = self.simple_user_view.as_view()
        response = await assume_async_view(view)(request, pk=user.pk)
        response.render()
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not await SimpleUser.objects.filter(pk=user.pk).aexists()

    async def test_destroy_404(self):
        assert await SimpleUser.objects.acount() == 0
        request = factory.delete("/666")
        view = self.simple_user_view.as_view()
        response = await assume_async_view(view)(request, pk=666)
        response.render()
        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = json.loads(response.content)
        assert data == {"detail": "No SimpleUser matches the given query."}

    async def test_destroy_hybrid_warn(self):
        user = await SimpleUser.objects.acreate(
            username="test", password="pass", age=88
        )
        request = factory.delete(f"/{user.pk}")
        view = self.simple_user_view_hybrid.as_view()
        with pytest.warns(
            PendingDeprecationWarning, match="Non async perform_destroy()?"
        ):
            response = await assume_async_view(view)(request, pk=user.pk)
            response.render()
            assert response.status_code == status.HTTP_204_NO_CONTENT
            assert not await SimpleUser.objects.filter(pk=user.pk).aexists()

    async def test_destroy_hybrid_no_warn(self):
        user = await SimpleUser.objects.acreate(
            username="test", password="pass", age=88
        )
        request = factory.delete(f"/{user.pk}")
        view = self.simple_user_view_hybrid_no_warn.as_view()
        with warnings.catch_warnings(record=True) as w:
            response = await assume_async_view(view)(request, pk=user.pk)
            assert len(w) == 0
        response.render()
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not await SimpleUser.objects.filter(pk=user.pk).aexists()
