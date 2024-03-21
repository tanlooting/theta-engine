from zoneinfo import ZoneInfo
import datetime

def get_date_today(tz : str = "US/Eastern") -> str:
    """Return today date in yyyymmdd format"""
    dt = datetime.datetime.now(ZoneInfo(tz))
    return dt.date().strftime("%Y%m%d")


def convert_str_date(date):
    """convert string (format: 20230623) to date"""
    return datetime.datetime.strptime(date,'%Y%m%d')