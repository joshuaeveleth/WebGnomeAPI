"""
Views for the Map objects.
"""
import ujson
import logging
import os

from cornice import Service
from pyramid.view import view_config
from pyramid.response import Response
from pyramid.httpexceptions import (HTTPBadRequest,
                                    HTTPNotFound,
                                    HTTPUnsupportedMediaType,
                                    HTTPNotImplemented)

from webgnome_api.common.views import (cors_exception,
                                       cors_response,
                                       get_object,
                                       cors_policy,
                                       process_upload)

from webgnome_api.common.common_object import (CreateObject,
                                               UpdateObject,
                                               ObjectImplementsOneOf,
                                               obj_id_from_url,
                                               obj_id_from_req_payload,
                                               get_file_path)

from webgnome_api.common.session_management import (init_session_objects,
                                                    get_session_objects,
                                                    get_session_object,
                                                    set_session_object)

from webgnome_api.common.helpers import JSONImplementsOneOf

map_api = Service(name='map', path='/map*obj_id',
                  description="Map API", cors_policy=cors_policy)

implemented_types = ('gnome.map.GnomeMap',
                     'gnome.map.MapFromBNA',
                     'gnome.map.ParamMap',
                     )

log = logging.getLogger(__name__)


@map_api.get()
def get_map(request):
    '''Returns a Gnome Map object in JSON.'''
    obj_ids = request.matchdict.get('obj_id')

    if (len(obj_ids) >= 2 and
            obj_ids[1] == 'geojson'):
        return get_geojson(request, implemented_types)
    else:
        return get_object(request, implemented_types)


@map_api.post()
def create_map_view(request):
    return create_map(request)


def create_map(request):
    '''Creates a Gnome Map object.'''
    log_prefix = 'req({0}): create_map():'.format(id(request))
    init_session_objects(request)

    try:
        json_request = ujson.loads(request.body)
    except:
        raise cors_exception(request, HTTPBadRequest)

    if not JSONImplementsOneOf(json_request, implemented_types):
        raise cors_exception(request, HTTPNotImplemented)

    if 'filename' in json_request:
        json_request['filename'] = get_file_path(request,
                                                 json_request=json_request)

    gnome_sema = request.registry.settings['py_gnome_semaphore']
    gnome_sema.acquire()
    log.info('  ' + log_prefix + 'semaphore acquired...')

    try:
        obj = CreateObject(json_request, get_session_objects(request))
    except:
        raise cors_exception(request, HTTPUnsupportedMediaType,
                             with_stacktrace=True)
    finally:
        gnome_sema.release()
        log.info('  ' + log_prefix + 'semaphore released...')

    set_session_object(obj, request)
    return obj.serialize()


@map_api.put()
def update_map(request):
    '''Updates a Gnome Map object.'''
    try:
        json_request = ujson.loads(request.body)
    except:
        raise cors_exception(request, HTTPBadRequest)

    if not JSONImplementsOneOf(json_request, implemented_types):
        raise cors_exception(request, HTTPNotImplemented)

    obj = get_session_object(obj_id_from_req_payload(json_request),
                             request)
    if obj:
        try:
            UpdateObject(obj, json_request, get_session_objects(request))
        except:
            raise cors_exception(request, HTTPUnsupportedMediaType,
                                 with_stacktrace=True)
    else:
        raise cors_exception(request, HTTPNotFound)

    set_session_object(obj, request)
    return obj.serialize()


@view_config(route_name='map_upload', request_method='OPTIONS')
def upload_map_options(request):
    return cors_response(request, request.response)


@view_config(route_name='map_upload', request_method='POST')
def upload_map(request):
    file_path = process_upload(request, 'new_map').split(os.path.sep)[-1]
    request.body = ujson.dumps({'obj_type': 'gnome.map.MapFromBNA',
                                'filename': file_path,
                                'refloat_halflife': 6.0,
                                'json_': 'webapi'
                                })
    map_obj = create_map(request)
    resp = Response(ujson.dumps(map_obj))

    return cors_response(request, resp)


def get_geojson(request, implemented_types):
    '''Returns the GeoJson for a Gnome Map object.'''
    obj = get_session_object(obj_id_from_url(request), request)

    if obj:
        if ObjectImplementsOneOf(obj, implemented_types):
            return obj.to_geojson()
        else:
            raise cors_exception(request, HTTPNotImplemented)
    else:
        raise cors_exception(request, HTTPNotFound)
