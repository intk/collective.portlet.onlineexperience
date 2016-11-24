from ComputedAttribute import ComputedAttribute
from plone.app.portlets.browser import formhelper
from plone.app.portlets.portlets import base
from plone.app.uuid.utils import uuidToObject, uuidToCatalogBrain
from plone.app.vocabularies.catalog import CatalogSource
from plone.i18n.normalizer.interfaces import IIDNormalizer
from plone.memoize.instance import memoize
from plone.portlet.collection import PloneMessageFactory as _
from plone.portlets.interfaces import IPortletDataProvider
from Products.CMFCore.utils import getToolByName
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from zExceptions import NotFound
from zope import schema
from zope.component import getUtility
from zope.interface import implements
import random
import json
import os
import pkg_resources

from zope.contentprovider.interfaces import IContentProvider
from plone.event.interfaces import IEvent
from zope.component import getMultiAdapter

COLLECTIONS = []

try:
    from plone.app.collection.interfaces import ICollection
    COLLECTIONS.append(ICollection.__identifier__)
except ImportError:
    pass

try:
    pkg_resources.get_distribution('plone.app.relationfield')
except pkg_resources.DistributionNotFound:
    HAS_RELATIONFIELD = False
else:
    from plone.app.relationfield.behavior import IRelatedItems
    HAS_RELATIONFIELD = True

class IOnlineExperiencePortlet(IPortletDataProvider):
    """A portlet which renders the results of a collection object.
    """

    header = schema.TextLine(
        title=_(u"Portlet header"),
        description=_(u"Title of the rendered portlet"),
        required=True)

    uid = schema.Choice(
        title=_(u"Target collection"),
        description=_(u"Find the collection which provides the items to list"),
        required=True,
        source=CatalogSource(portal_type=('Topic', 'Collection')),
        )

    limit = schema.Int(
        title=_(u"Limit"),
        description=_(u"Specify the maximum number of items to show in the "
                      u"portlet. Leave this blank to show all items."),
        required=False)

    random = schema.Bool(
        title=_(u"Select random items"),
        description=_(u"If enabled, items will be selected randomly from the "
                      u"collection, rather than based on its sort order."),
        required=True,
        default=False)

    show_more = schema.Bool(
        title=_(u"Show more... link"),
        description=_(u"If enabled, a more... link will appear in the footer "
                      u"of the portlet, linking to the underlying "
                      u"Collection."),
        required=True,
        default=True)

    show_dates = schema.Bool(
        title=_(u"Show dates"),
        description=_(u"If enabled, effective dates will be shown underneath "
                      u"the items listed."),
        required=True,
        default=False)

    exclude_context = schema.Bool(
        title=_(u"Exclude the Current Context"),
        description=_(
            u"If enabled, the listing will not include the current item the "
            u"portlet is rendered for if it otherwise would be."),
        required=True,
        default=True)


class Assignment(base.Assignment):
    """
    Portlet assignment.
    This is what is actually managed through the portlets UI and associated
    with columns.
    """

    implements(IOnlineExperiencePortlet)

    header = u""
    limit = None
    random = False
    show_more = True
    show_dates = False
    exclude_context = False

    # bbb
    target_collection = None

    def __init__(self, header=u"", uid=None, limit=None,
                 random=False, show_more=True, show_dates=False,
                 exclude_context=True):
        self.header = header
        self.uid = uid
        self.limit = limit
        self.random = random
        self.show_more = show_more
        self.show_dates = show_dates
        self.exclude_context = exclude_context

    @property
    def title(self):
        """This property is used to give the title of the portlet in the
        "manage portlets" screen. Here, we use the title that the user gave.
        """
        return self.header

    def _uid(self):
        # This is only called if the instance doesn't have a uid
        # attribute, which is probably because it has an old
        # 'target_collection' attribute that needs to be converted.
        path = self.target_collection
        portal = getToolByName(self, 'portal_url').getPortalObject()
        try:
            collection = portal.unrestrictedTraverse(path.lstrip('/'))
        except (AttributeError, KeyError, TypeError, NotFound):
            return
        return collection.UID()
    uid = ComputedAttribute(_uid, 1)


class Renderer(base.Renderer):

    _template = ViewPageTemplateFile('online_experience.pt')
    render = _template

    def __init__(self, *args):
        base.Renderer.__init__(self, *args)

    @property
    def available(self):
        return len(self.results())

    def collection_url(self):
        collection = self.collection()
        if collection is None:
            return None
        else:
            return collection.absolute_url()

    def css_class(self):
        header = self.data.header
        normalizer = getUtility(IIDNormalizer)
        return "portlet-onlineexperience-%s" % normalizer.normalize(header)


    def find_orientation(self, item):
        if type(item) == str:
            if item == "L":
                return "landscape"
            else:
                return "portrait"

        item_class = ""
        if item.portal_type == "Image":
            image_obj = item.getObject()
            if getattr(image_obj, 'image', None):
                try:
                    w, h = image_obj.image.getImageSize()
                    if w > h:
                        item_class = "%s" %('landscape')
                    else:
                        item_class = "%s" %('portrait')
                except:
                    return item_class
        elif item.hasMedia:
            image = uuidToCatalogBrain(item.leadMedia)
            image_obj = image.getObject()
            if getattr(image_obj, 'image', None):
                try:
                    w, h = image_obj.image.getImageSize()
                    if w > h:
                        item_class = "%s" %('landscape')
                    else:
                        item_class = "%s" %('portrait')
                except:
                    return item_class

        return item_class

    def getImageProperties(self, item):
        link = item.getURL()+"/view"
        title = item.Title
        description = item.Description

        try:
            if item.portal_type == "Image":
                image = item.getObject()
                parent = image.aq_parent
                if parent.portal_type == "Folder":
                    if parent.id == "slideshow":
                        obj = parent.aq_parent
                        if obj.portal_type == "Object":
                            title = obj.title
                            description = obj.description
                            link = obj.absolute_url()

        except:
            raise

        return {"link": link, "title": title, "description": description}

    def getImageClass(self, item, has_media=False):

        item_class = "entry"

        if item.portal_type == "Image":
            image_obj = item.getObject()
            if getattr(image_obj, 'image', None):
                try:
                    w, h = image_obj.image.getImageSize()
                    if w > h:
                        item_class = "%s %s" %(item_class, 'landscape')
                    else:
                        item_class = "%s %s" %(item_class, 'portrait')
                except:
                    return item_class
        elif has_media:
            image = uuidToCatalogBrain(item.leadMedia)
            image_obj = image.getObject()
            if getattr(image_obj, 'image', None):
                try:
                    w, h = image_obj.image.getImageSize()
                    if w > h:
                        item_class = "%s %s" %(item_class, 'landscape')
                    else:
                        item_class = "%s %s" %(item_class, 'portrait')
                except:
                    return item_class

        return item_class
        
    def pairItems(self, results):
        # L P L L L P P P
        TEST_INPUT = ["L", "P", "L", "L", "L", "P", "P", "P"]
        FIRST_ITEM = 0
        
        items = results
        total_items = len(items)
        items_checked = []
        final_patterns = []

        right = True
        previous_pair = ""

        for i in range(total_items):
            if i not in items_checked:

                right_pattern = "right" if right else "left"
                pattern = {
                    "size": "small",
                    "orientation": self.find_orientation(items[i]),
                    "position": "pair",
                    "clearfix": False,
                    "item": items[i],
                    "right": right_pattern,
                    "bottom": ""
                }
               
                if i == FIRST_ITEM:
                    pattern['position'] = "single"
                    pattern['size'] = "big"
                    final_patterns.append(pattern)
                    items_checked.append(i)
                    if right:
                        right = False
                    else:
                        right = True
                else:
                    if i+1 < total_items:
                        next_orientation = self.find_orientation(items[i+1])

                        if next_orientation == pattern["orientation"] == "landscape":
                            pattern["position"] = "single"
                            pattern["size"] = "big"
                            final_patterns.append(pattern)
                            if right:
                                right = False
                            else:
                                right = True

                            previous_pair = ""
                        else:
                            new_pattern = {
                                "size": pattern['size'],
                                "orientation": pattern['orientation'],
                                "position": "pair",
                                "clearfix": True,
                                "item": items[i+1],
                                "right": pattern['right'],
                                "bottom": pattern['bottom']
                            }
                            new_pattern["orientation"] = next_orientation

                            if next_orientation == pattern['orientation'] == "portrait":
                                pattern['size'] = "big"
                                new_pattern['size'] = "big"

                            if not previous_pair:
                                if right:
                                    pattern['bottom'] = "bottom"
                                    new_pattern['bottom'] = "up"
                                else:
                                    new_pattern['bottom'] = "bottom"
                                    pattern['bottom'] = "up"
                            else:
                                if previous_pair == "bottom":
                                    pattern['bottom'] = "up"
                                    new_pattern['bottom'] = "bottom"
                                    previous_pair = "bottom"
                                else:
                                    pattern['bottom'] = "bottom"
                                    new_pattern['bottom'] = "up"
                                    previous_pair = "up"

                            final_patterns.append(pattern)
                            final_patterns.append(new_pattern)
                            items_checked.append(i)
                            items_checked.append(i+1)
                    else:
                        pattern['position'] = "single"
                        pattern['size'] = "big"
                        final_patterns.append(pattern)
            else:
                pass

        return final_patterns

    def getImageObject(self, item):
        if item.portal_type == "Image":
            return item.getURL()+"/@@images/image/large"
        if item.leadMedia != None:
            uuid = item.leadMedia
            media_object = uuidToCatalogBrain(uuid)
            if media_object:
                return media_object.getURL()+"/@@images/image/large"
            else:
                return None
        else:
            return None

    def is_event(self, obj):
        if getattr(obj, 'getObject', False):
            obj = obj.getObject()
        return IEvent.providedBy(obj)

    def formatted_date(self, obj):
        item = obj.getObject()
        provider = getMultiAdapter(
            (self.context, self.request, self),
            IContentProvider, name='formatted_date'
        )
        return provider(item)

    @memoize
    def results(self):
        if self.data.random:
            return self._random_results()
        else:
            return self._standard_results()

    def _standard_results(self):
        results = []
        collection = self.collection()
        if collection is not None:
            context_path = '/'.join(self.context.getPhysicalPath())
            exclude_context = getattr(self.data, 'exclude_context', False)
            limit = self.data.limit
            if limit and limit > 0:
                # pass on batching hints to the catalog
                results = collection.queryCatalog(
                    batch=True, b_size=limit  + exclude_context)
                results = results._sequence
            else:
                results = collection.queryCatalog()
            if exclude_context:
                results = [
                    brain for brain in results
                    if brain.getPath() != context_path]
            if limit and limit > 0:
                results = results[:limit]
        return results

    def _random_results(self):
        # intentionally non-memoized
        results = []
        collection = self.collection()
        if collection is not None:
            context_path = '/'.join(self.context.getPhysicalPath())
            exclude_context = getattr(self.data, 'exclude_context', False)
            results = collection.queryCatalog(sort_on=None, batch=False)
            if results is None:
                return []
            limit = self.data.limit and min(len(results), self.data.limit) or 1

            if exclude_context:
                results = [
                    brain for brain in results
                    if brain.getPath() != context_path]
            if len(results) < limit:
                limit = len(results)
            results = random.sample(results, limit)

        return results

    @memoize
    def collection(self):
        return uuidToObject(self.data.uid)

    def include_empty_footer(self):
        """
        Whether or not to include an empty footer element when the more
        link is turned off.
        Always returns True (this method provides a hook for
        sub-classes to override the default behaviour).
        """
        return True

    def getLeadMediaURL(self, item, scale="large"):
        if item.portal_type == "Image":
            url = item.getURL()
            if url:
                return "%s/@@images/image/%s" %(item.getURL(), scale)
            else:
                return None
        if item.leadMedia != None:
            media_object = uuidToCatalogBrain(item.leadMedia)
            if media_object:
                return "%s/@@images/image/%s" %(media_object.getURL(), scale)
            else:
                return None
        return None

    def getStreetViewOptions(self, item):
        if item.portal_type == "StreetView":
            obj = item.getObject()
            streetview_options = getattr(obj, 'streetview_settings', None)
            if streetview_options:
                streetview_options_dict = json.loads(streetview_options)
                if streetview_options_dict:
                    return streetview_options_dict[0]
                else:
                    return None
            else:
                return None
        else:
            return None

    def getAudioURL(self, item):
        if item:
            ext = ''
            url = item.getURL()
            filename = item.getFilename()
            if filename:
                extension = os.path.splitext(filename)[1]
                if not url.endswith(extension):
                    ext = "?e=%s" % extension
            return url + ext
        else:
            return ""

    def getAudioFile(self, item):
        related_items = self.getRelatedItems(item)
        if len(related_items):
            audio_file = related_items[0]
            if audio_file.portal_type == "File":
                return audio_file
            else:
                return None
        else:
            return None
        return None

    def getRelatedItems(self, item):
        if HAS_RELATIONFIELD and IRelatedItems.providedBy(item):
            res = []
            related = item.relatedItems
            if not related:
                return ()
            res = self.related2brains(related)
            return res
        else:
            return []

    def related2brains(self, related):
        """Return a list of brains based on a list of relations. Will filter
        relations if the user has no permission to access the content.
        :param related: related items
        :type related: list of relations
        :return: list of catalog brains
        """
        catalog = getToolByName(self.context, 'portal_catalog')
        brains = []
        for r in related:
            path = r.to_path
            # the query will return an empty list if the user
            # has no permission to see the target object
            brains.extend(catalog(path=dict(query=path, depth=0)))
        return brains


class AddForm(base.AddForm):

    schema = IOnlineExperiencePortlet
    label = _(u"Add Online Experience Portlet")
    description = _(u"This portlet renders the Online Experience with items from a "
                    u"Collection.")

    def create(self, data):
        return Assignment(**data)


class EditForm(base.EditForm):
    schema = IOnlineExperiencePortlet
    label = _(u"Edit Online Experience Portlet")
    description = _(u"This portlet renders the Online Experience with items from a "
                    u"Collection.")
