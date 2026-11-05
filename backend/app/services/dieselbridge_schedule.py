"""Bounded shop-local backup slots; signed events are never business-hour gated."""
from dataclasses import dataclass
from datetime import datetime,time,timedelta,timezone,date
import hashlib,json,os
from zoneinfo import ZoneInfo,ZoneInfoNotFoundError


@dataclass(frozen=True)
class ShopSchedule:
    timezone_name: str = 'America/New_York'
    open_hour: int = 9
    close_hour: int = 19
    interval_hours: int = 1
    weekdays: tuple = (0,1,2,3,4,5,6)
    closed_dates: tuple = ()

    @property
    def zone(self):return ZoneInfo(self.timezone_name)

    def slots(self,day):
        if day.weekday() not in self.weekdays or day.isoformat() in self.closed_dates:return []
        hours=list(range(self.open_hour,self.close_hour+1,self.interval_hours))
        if hours[-1]!=self.close_hour:hours.append(self.close_hour)
        result=[]
        for hour in hours:
            local=datetime.combine(day,time(hour),tzinfo=self.zone)
            utc=local.astimezone(timezone.utc)
            # Skip nonexistent wall times rather than shifting them across DST.
            if utc.astimezone(self.zone).replace(tzinfo=None)!=local.replace(tzinfo=None):continue
            result.append(utc)
        return result

    def next_after(self,now):
        local=now.astimezone(self.zone)
        for offset in range(15+7*len(self.closed_dates)):
            for slot in self.slots(local.date()+timedelta(days=offset)):
                if slot>now:return slot
        raise ValueError('No business backup slot is available.')

    def due_slot(self,now):
        local=now.astimezone(self.zone);slots=self.slots(local.date())
        # Closing check belongs to the closing minute; no late overnight replay.
        if not slots or now<slots[0] or now>=slots[-1]+timedelta(minutes=1):return None
        return max((slot for slot in slots if slot<=now),default=None)

    def key(self,slot):
        config={'timezone':self.timezone_name,'open_hour':self.open_hour,'close_hour':self.close_hour,
                'interval_hours':self.interval_hours,'weekdays':self.weekdays,'closed_dates':self.closed_dates}
        version=hashlib.sha256(json.dumps(config,sort_keys=True).encode()).hexdigest()[:16]
        return 'backup:v2:'+version+':'+slot.astimezone(timezone.utc).isoformat()


def load_schedule():
    try:
        value=json.loads(os.getenv('ELIS_DIESELBRIDGE_BACKUP_SCHEDULE','{}'))
        allowed={'timezone','open_hour','close_hour','interval_hours','weekdays','closed_dates'}
        if not isinstance(value,dict) or set(value)-allowed:raise ValueError()
        zone=value.get('timezone','America/New_York');ZoneInfo(zone)
        opening=value.get('open_hour',9);closing=value.get('close_hour',19);interval=value.get('interval_hours',1)
        days=value.get('weekdays',list(range(7)));closed=value.get('closed_dates',[])
        if any(type(v) is not int for v in (opening,closing,interval)) or not 0<=opening<closing<=23 or not 1<=interval<=12:raise ValueError()
        if not isinstance(days,list) or not days or len(days)>7 or any(type(v) is not int or not 0<=v<=6 for v in days) or len(set(days))!=len(days):raise ValueError()
        if not isinstance(closed,list) or len(closed)>366 or any(not isinstance(v,str) or date.fromisoformat(v).isoformat()!=v for v in closed):raise ValueError()
        return ShopSchedule(zone,opening,closing,interval,tuple(sorted(days)),tuple(sorted(set(closed))))
    except (ValueError,TypeError,ZoneInfoNotFoundError):
        raise ValueError('Invalid DBN backup schedule configuration.') from None
