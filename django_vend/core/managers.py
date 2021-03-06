from django.db import models
from django.utils import timezone

import requests

from django_vend.core.exceptions import VendSyncError


class AbstractVendAPISingleObjectManager(models.Manager):
    def synchronise(self, retailer, object_id):
        return self._retrieve_object_from_api(retailer, object_id)

class AbstractVendAPICollectionManager(models.Manager):
    def synchronise(self, retailer):
        return self._retrieve_collection_from_api(retailer)

class AbstractVendAPIManager(models.Manager):
    def synchronise(self, retailer, object_id=None):
        if object_id:
            return self._retrieve_object_from_api(retailer, object_id)
        else:
            return self._retrieve_collection_from_api(retailer)

class VendAPIManagerMixin(object):

    sync_exception = VendSyncError

    def get_dict_value(self, dict_obj, key, exception=None, required=True):
        if exception is None:
            exception = self.sync_exception
        value = dict_obj.get(key)
        if not value and required:
            raise exception('dict_obj does not contain key {}'.format(key))


        return value

    def _retrieve_from_api(self, retailer, url):
        exception = self.sync_exception

        headers = {
            'Authorization': 'Bearer {}'.format(retailer.access_token),
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }
        try:
            result = requests.get(url, headers=headers)
        except requests.exceptions.RequestException as e:
            raise exception(e)
        if result.status_code != requests.codes.ok:
            raise exception(
                'Received {} status from Vend API'.format(result.status_code))
        try:
            data = result.json()
        except ValueError as e:
            raise exception(e)
        return data

    def get_inner_json(self, obj, container_name):
        inner = None
        if container_name is not None:
            try:
                inner = obj[container_name]
            except KeyError as e:
                raise self.sync_exception(e)
        return inner or obj


class VendAPISingleObjectManagerMixin(VendAPIManagerMixin):

    resource_object_url = None
    json_object_name = None

    def _retrieve_object_from_api(self, retailer, object_id, defaults=None):
        # Call API
        url = self.resource_object_url.format(retailer.name, object_id)
        data = self._retrieve_from_api(retailer, url)

        data = self.get_inner_json(data, self.json_object_name)

        return self.parse_object(retailer, data, defaults)

    def parse_json_object(self, json_obj):
        raise NotImplementedError('parse_json_object method must be '
                                  'implemented by {}'.format(
                                      self.__class__.__name__))

    def parse_object(self, retailer, result, additional_defaults=None):
        uid = self.get_dict_value(result, 'id')
        defaults = self.parse_json_object(result)
        defaults['retailer'] = retailer

        if additional_defaults:
            for key in additional_defaults:
                defaults[key] = additional_defaults[key]

        defaults['retrieved'] = timezone.now()

        obj, created = self.update_or_create(uid=uid, defaults=defaults)
        return created

class VendAPICollectionManagerMixin(VendAPIManagerMixin):

    resource_collection_url = None
    json_collection_name = None

    def _retrieve_collection_from_api(self, retailer):
        # Call API
        url = self.resource_collection_url.format(retailer.name)
        data = self._retrieve_from_api(retailer, url)

        data = self.get_inner_json(data, self.json_collection_name)

        # Save to DB & Return saved objects
        return self.parse_collection(retailer, data)

    def parse_json_collection_object(self, json_obj):
        raise NotImplementedError('parse_json_collection_object method must be '
                                  'implemented by {}'.format(
                                      self.__class__.__name__))

    def parse_collection(self, retailer, result):
        created = False

        for object_stub in result:
            uid = self.get_dict_value(object_stub, 'id')

            defaults = self.parse_json_collection_object(object_stub)
            defaults['retailer'] = retailer
            defaults['retrieved'] = timezone.now()

            obj, created_ = self.update_or_create(uid=uid, defaults=defaults)
            created = created or created_

        return created

class BaseVendAPIManager(AbstractVendAPIManager,
                         VendAPICollectionManagerMixin,
                         VendAPISingleObjectManagerMixin):
    """
    Simple implementation of a Manager class for a django model that contains
    data retrieved from the Vend API.
    """
    def parse_json_collection_object(self, json_obj):
        return self.parse_json_object(json_obj)

class BaseVendAPISingleObjectManager(AbstractVendAPISingleObjectManager,
                                     VendAPISingleObjectManagerMixin):
    """
    Simple implementation of a Manager class for a django model for which
    individual instances can be retrieved from the Vend API.
    """
    pass

class BaseVendAPICollectionManager(AbstractVendAPICollectionManager,
                                   VendAPICollectionManagerMixin):
    """
    Simple implementation of a Manager class for a django model for which
    instances can only be retrieved from the Vend API in multiples.
    """
    pass
