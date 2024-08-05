from django.contrib.auth.models import User
from django.db import models


class Order(models.Model):
    name = models.TextField()
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return f"Order<{self.name} by {self.user}>"


class Additional(models.Model):
    nickname = models.TextField()
    user = models.OneToOneField(User, primary_key=True, on_delete=models.CASCADE)
