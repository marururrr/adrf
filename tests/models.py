from django.contrib.auth.models import User
from django.db import models


class Order(models.Model):
    name = models.TextField()
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    def __str__(self):
        return f"Order<{self.name} by {self.user.username}>"


class Delivery(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, null=True)
    deliverer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return f"Delivery<{self.order} by {self.deliverer}>"


class Additional(models.Model):
    nickname = models.TextField()
    user = models.OneToOneField(User, primary_key=True, on_delete=models.CASCADE)
