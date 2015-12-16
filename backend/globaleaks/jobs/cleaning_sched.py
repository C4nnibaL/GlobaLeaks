# -*- coding: UTF-8
#
#   cleaning_sched
#   **************
#
# Implementation of the cleaning operations (delete incomplete submission,
# delete expired tips, etc)

from datetime import timedelta
from twisted.internet.defer import inlineCallbacks

from globaleaks.orm import transact, transact_ro
from globaleaks.handlers import admin
from globaleaks.handlers.rtip import db_delete_itip, serialize_rtip
from globaleaks.jobs.base import GLJob
from globaleaks.models import InternalTip, Receiver, ReceiverTip, Stats
from globaleaks.settings import GLSettings
from globaleaks.utils.utility import log, datetime_now


__all__ = ['CleaningSchedule']

"""TODOTODOTODO
class ExpiringRTipEvent(EventLogger):
    def __init__(self):
        EventLogger.__init__(self)
        self.trigger = 'ExpiringTip'

    @transact
    def process_events(self, store):
        for receiver in store.find(Receiver):
            user_threshold = datetime_now() - timedelta(seconds=receiver.tip_expiration_threshold)
            for rtip in store.find(ReceiverTip, ReceiverTip.receiver_id == receiver.id):
                if rtip.internaltip.expiration_date < user_threshold:
                    pass
                    self.process_event(store, rtip)

        db_save_events_on_db(store, self.events)

        log.debug("Cleaning: generated %d notification events of type %s" %
                  (len(self.events), self.trigger))

    def process_event(self, store, rtip):
        do_mail, receiver_desc = self.import_receiver(rtip.receiver)

        context_desc = admin.admin_serialize_context(store,
                                                     rtip.internaltip.context,
                                                     self.language)

        expiring_tip_desc = serialize_rtip(store, rtip, self.language)
"""

class CleaningSchedule(GLJob):
    name = "Cleaning"

    @transact_ro
    def get_cleaning_map(self, store):
        subjects = store.find(InternalTip, InternalTip.expiration_date < datetime_now())

        itip_id_list = []
        for itip in subjects:
            itip_id_list.append(unicode(itip.id))

        if itip_id_list:
            log.info("Removal of %d InternalTips starts soon" % subjects.count())
        return itip_id_list

    @transact
    def perform_cleaning(self, store, itip_id):
        itip = store.find(InternalTip, InternalTip.id == itip_id).one()
        # Is happen that itip was NoneType, so, we are managing this condition
        if itip:
            db_delete_itip(store, itip)
        else:
            log.err("DB Inconsistency ? InternalTip to be deleted %s is None" % itip_id)

    @transact
    def perform_stats_cleaning(self, store):
        # delete stats older than 3 months
        store.find(Stats, Stats.start < datetime_now() - timedelta(3*(365/12))).remove()

    @transact
    def clean_notified_events(self, store):
        pass

    @inlineCallbacks
    def operation(self):
        """
        This function, checks all the InternalTips and their expiration date.
        if expired InternalTips are found, it removes that along with
        all the related DB entries comment and tip related.
        """
        # Reset the exception tracking variable of GLSettings
        GLSettings.exceptions = {}
        GLSettings.exceptions_email_count = 0

        itip_list_ids = yield self.get_cleaning_map()
        for itip_id in itip_list_ids:
            yield self.perform_cleaning(itip_id)

        yield self.perform_stats_cleaning()
        #yield ExpiringRTipEvent().process_events()

        yield self.clean_notified_events()
