import os
import sys
import json
import time
import logging
import django
from datetime import datetime

# ─── Django setup (phải chạy trước import models) ─────────
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.conf import settings

import paho.mqtt.client as mqtt
from apscheduler.executors.pool import ThreadPoolExecutor   # ThreadPool để share Django ORM
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.schedulers.blocking import BlockingScheduler

# ─── Logging ───────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s — %(message)s',
    datefmt='%H:%M:%S',
)
logger = logging.getLogger('mqtt_service')

# ─── MQTT Config (đọc từ settings.py) ─────────────────────
MQTT_BROKER   = getattr(settings, 'MQTT_BROKER',   'localhost')
MQTT_PORT     = getattr(settings, 'MQTT_PORT',     1883)
MQTT_USERNAME = getattr(settings, 'MQTT_USERNAME', None)
MQTT_PASSWORD = getattr(settings, 'MQTT_PASSWORD', None)

# Topics
# Django  →  ESP32 :  smart_box/locker/<locker_id>
#   payload: {"compartment": <number>, "token": "<unlock_token>", "ts": <epoch>}
# ESP32   →  Django:  smart_box/status/<compartment_id>
#   payload: {"status": "opened|closed|error", "ts": <epoch>}
TOPIC_UNLOCK_PUB = 'smart_box/locker/{locker_id}'
TOPIC_STATUS_SUB = 'smart_box/status/#'

# Global MQTT client (dùng bởi publish_unlock từ scheduler/view)
mqtt_client: mqtt.Client = None


# ═══════════════════════════════════════════════════════════
# MQTT CALLBACKS
# ═══════════════════════════════════════════════════════════

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        logger.info(f'[MQTT] Connected to broker {MQTT_BROKER}:{MQTT_PORT}')
        client.subscribe(TOPIC_STATUS_SUB, qos=1)
        logger.info(f'[MQTT] Subscribed to {TOPIC_STATUS_SUB}')
    else:
        codes = {1: 'bad protocol', 2: 'bad client id', 3: 'broker unavailable',
                 4: 'bad credentials', 5: 'not authorised'}
        logger.error(f'[MQTT] Connection refused — {codes.get(rc, f"rc={rc}")}')


def on_disconnect(client, userdata, rc):
    if rc != 0:
        logger.warning(f'[MQTT] Unexpected disconnect (rc={rc}) — will auto-reconnect')


def on_message(client, userdata, msg):
    """Nhận status từ ESP32 (mở cửa / đóng cửa / lỗi)."""
    try:
        payload = json.loads(msg.payload.decode('utf-8'))
        parts   = msg.topic.split('/')
        # Topic: smart_box/status/<compartment_id>
        if len(parts) == 3 and parts[0] == 'smart_box' and parts[1] == 'status':
            compartment_id = int(parts[2])
            _handle_hardware_status(compartment_id, payload)
    except Exception as e:
        logger.error(f'[MQTT] on_message error: {e}')


def _handle_hardware_status(compartment_id: int, payload: dict):
    """
    Xử lý trạng thái phần cứng gửi về.
    - 'opened' : ESP32 xác nhận đã mở cửa ngăn
    - 'closed' : cửa đã đóng lại (tự khóa)
    - 'error'  : lỗi phần cứng
    Server KHÔNG gửi lệnh khoá — phần cứng tự khoá sau khi đóng cửa.
    """
    status = payload.get('status', '')
    ts     = payload.get('ts', 0)
    logger.info(f'[Hardware] Compartment {compartment_id} → status={status!r} ts={ts}')

    if status == 'error':
        logger.error(f'[Hardware] Compartment {compartment_id} reported error: {payload}')
        # TODO: gửi alert cho admin qua email / push notification

    elif status == 'opened':
        logger.info(f'[Hardware] Compartment {compartment_id} opened successfully')
        # Có thể update DB nếu cần ghi lịch sử "mở lúc ..."

    elif status == 'closed':
        logger.info(f'[Hardware] Compartment {compartment_id} closed & locked by hardware')
        # Phần cứng tự khoá — không cần server can thiệp


# ═══════════════════════════════════════════════════════════
# PUBLISH HELPER  (dùng bởi view unlock_compartment)
# ═══════════════════════════════════════════════════════════

def publish_unlock(locker_id: int, compartment_number: int, unlock_token=None) -> bool:
    """
    Gửi lệnh mở ngăn đến ESP32 qua MQTT.
    Trả về True nếu publish thành công.
    """
    global mqtt_client
    if mqtt_client is None or not mqtt_client.is_connected():
        logger.warning('[MQTT] Client not connected — unlock command NOT sent')
        return False

    topic   = TOPIC_UNLOCK_PUB.format(locker_id=locker_id)
    payload = json.dumps({
        'compartment': compartment_number,
        'token': str(unlock_token) if unlock_token else None,
        'ts':    int(time.time()),
    })
    result = mqtt_client.publish(topic, payload, qos=1)
    if result.rc == mqtt.MQTT_ERR_SUCCESS:
        logger.info(f'[MQTT] Unlock → {topic}  payload={payload}')
        return True
    else:
        logger.error(f'[MQTT] Publish failed rc={result.rc}')
        return False


# ═══════════════════════════════════════════════════════════
# SCHEDULER JOBS
# ═══════════════════════════════════════════════════════════

def schedule_complete_event():
    """
    Chạy mỗi 15 giây.
    - Kiểm tra health của MQTT connection
    - (Mở rộng) retry các unlock request bị thất bại
    """
    epoch_time_now = int((datetime.now() - datetime(1970, 1, 1)).total_seconds())
    logger.info(f'[Scheduler] Tick | ts={epoch_time_now} | mqtt_connected={mqtt_client.is_connected() if mqtt_client else False}')

    # Ví dụ kiểm tra DB — có thể thêm logic retry sau
    try:
        from bookings.models import Booking
        active_count = Booking.objects.filter(status='active').count()
        logger.info(f'[Scheduler] Active bookings: {active_count}')
    except Exception as e:
        logger.error(f'[Scheduler] DB check error: {e}')


# ═══════════════════════════════════════════════════════════
# SCHEDULER SETUP  (giữ nguyên cấu trúc template gốc)
# ═══════════════════════════════════════════════════════════

def create_scheduler():
    jobstores = {'default': MemoryJobStore()}
    executors = {
        # ThreadPoolExecutor thay vì ProcessPoolExecutor
        # vì các job cần truy cập Django ORM (cùng process)
        'default': ThreadPoolExecutor(max_workers=4)
    }
    job_defaults = {
        'coalesce': True,
        'max_instances': 1,          # tránh chạy đồng thời nhiều instance
        'misfire_grace_time': 60,
    }
    scheduler = BlockingScheduler(
        jobstores=jobstores,
        executors=executors,
        job_defaults=job_defaults,
        timezone='UTC',
    )
    return scheduler


def config_job(scheduler):
    scheduler.add_job(schedule_complete_event, 'interval', seconds=15)
    return scheduler


# ═══════════════════════════════════════════════════════════
# MAIN SERVICE LOOP
# ═══════════════════════════════════════════════════════════

def start_scheduler():
    """Entry point — giữ cấu trúc giống template gốc."""
    global mqtt_client
    while True:
        try:
            # 1) Kết nối MQTT
            client = mqtt.Client(client_id='smart_box_server', clean_session=True)
            if MQTT_USERNAME:
                client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
            client.on_connect    = on_connect
            client.on_disconnect = on_disconnect
            client.on_message    = on_message

            logger.info(f'[Service] Connecting to MQTT broker {MQTT_BROKER}:{MQTT_PORT} ...')
            client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
            client.loop_start()    # MQTT chạy thread riêng (non-blocking)
            mqtt_client = client   # expose cho publish_unlock

            # 2) Khởi scheduler (blocking — chiếm main thread)
            logger.info('[Service] MQTT connected. Starting scheduler...')
            scheduler = create_scheduler()
            config_job(scheduler)
            scheduler.start()

        except (KeyboardInterrupt, SystemExit):
            logger.info('[Service] Shutting down gracefully...')
            if mqtt_client:
                mqtt_client.loop_stop()
                mqtt_client.disconnect()
            break
        except Exception as e:
            logger.error(f'[Service] Error: {e}')
            logger.info('[Service] Restarting in 10s...')
            if mqtt_client:
                try:
                    mqtt_client.loop_stop()
                    mqtt_client.disconnect()
                except Exception:
                    pass
            time.sleep(10)


if __name__ == '__main__':
    start_scheduler()
