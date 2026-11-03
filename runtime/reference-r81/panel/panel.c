#include "kms.h"
#include "ui.h"

#include <errno.h>
#include <fcntl.h>
#include <grp.h>
#include <linux/input.h>
#include <math.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/prctl.h>
#include <time.h>
#include <unistd.h>

static volatile sig_atomic_t stopped;

struct pointer_stream {
    int fd;
    struct input_absinfo x, y;
    lv_indev_data_t current;
    bool pressed;
    bool dropped;
    double x_gain, x_offset, y_gain, y_offset;
};

static bool parse_coefficient(const char *text, double minimum, double maximum, double *value)
{
    char *end;
    errno = 0;
    *value = strtod(text, &end);
    return end != text && !*end && !errno && isfinite(*value) && *value >= minimum && *value <= maximum;
}

static int sensor_direction(void)
{
    const char *path = "/run/v30-screen-orientation/direction";
#ifdef V30_ORIENTATION_FIXTURE
    const char *fixture = getenv("V30_PANEL_ORIENTATION_FIXTURE");
    if(fixture) path = fixture;
#endif
    int fd = open(path, O_RDONLY | O_CLOEXEC | O_NOFOLLOW);
    if(fd < 0) return -1;
    char data[3];
    ssize_t size = read(fd, data, sizeof(data));
    close(fd);
    return size == 2 && data[0] >= '0' && data[0] <= '3' && data[1] == '\n' ? data[0] - '0' : -1;
}

/* fbcon describes physical orientation. LVGL rotates the rendered buffer
 * the other way to keep it upright on the native portrait scanout. */
static const lv_display_rotation_t rotations[] = {
    LV_DISPLAY_ROTATION_0, LV_DISPLAY_ROTATION_270, LV_DISPLAY_ROTATION_180, LV_DISPLAY_ROTATION_90,
};

static int32_t scale_axis(const struct input_absinfo *axis, int32_t limit)
{
    int32_t value = LV_CLAMP(axis->minimum, axis->value, axis->maximum);
    return (int32_t)(((int64_t)value - axis->minimum) * limit /
                     ((int64_t)axis->maximum - axis->minimum));
}

static void read_pointer(lv_indev_t *indev, lv_indev_data_t *data)
{
    struct pointer_stream *touch = lv_indev_get_driver_data(indev);
    struct input_event event;
    *data = touch->current;
    for(unsigned i = 0; i < 128; i++) {
        ssize_t length = read(touch->fd, &event, sizeof(event));
        if(length < 0 && errno == EINTR) continue;
        if(length != sizeof(event)) return;
        if(event.type == EV_SYN && event.code == SYN_DROPPED) {
            lv_indev_reset(indev, NULL);
            touch->pressed = false;
            touch->dropped = true;
            touch->current.state = LV_INDEV_STATE_RELEASED;
            *data = touch->current;
        } else if(event.type == EV_SYN && event.code == SYN_REPORT) {
            if(touch->dropped) {
                struct input_absinfo x, y;
                if(ioctl(touch->fd, EVIOCGABS(ABS_X), &x) == 0) touch->x.value = x.value;
                if(ioctl(touch->fd, EVIOCGABS(ABS_Y), &y) == 0) touch->y.value = y.value;
                touch->dropped = false;
            }
            int32_t x = scale_axis(&touch->y, 2879);
            int32_t y = 1439 - scale_axis(&touch->x, 1439);
            x = lround(touch->x_gain * x + touch->x_offset);
            y = lround(touch->y_gain * y + touch->y_offset);
            touch->current.point.x = 1439 - LV_CLAMP(0, y, 1439);
            touch->current.point.y = LV_CLAMP(0, x, 2879);
            touch->current.state = touch->pressed ? LV_INDEV_STATE_PRESSED : LV_INDEV_STATE_RELEASED;
            *data = touch->current;
            data->continue_reading = true;
            return;
        } else if(!touch->dropped) {
            /* stmfts emits the primary pointer at frame sync. Mixing MT slots
             * with this stream lets another finger move or release that pointer. */
            if(event.type == EV_ABS && event.code == ABS_X) touch->x.value = event.value;
            else if(event.type == EV_ABS && event.code == ABS_Y) touch->y.value = event.value;
            else if(event.type == EV_KEY && event.code == BTN_TOUCH) touch->pressed = event.value == 1;
        }
    }
}

static void stop_on_signal(int signal_number)
{
    (void)signal_number;
    stopped = 1;
}

static void return_to_console(void)
{
    puts("return_button=1");
    stopped = 1;
}

static uint32_t ticks(void)
{
    struct timespec now;
    clock_gettime(CLOCK_MONOTONIC, &now);
    return (uint32_t)((uint64_t)now.tv_sec * 1000 + now.tv_nsec / 1000000);
}

int main(int argc, char **argv)
{
    if(argc != 12) {
        fprintf(stderr, "Usage: %s DRM_DEVICE DSI_CONNECTOR TOUCH_DEVICE UID GID X_GAIN X_OFFSET Y_GAIN Y_OFFSET CONTROL_FD MODE\n", argv[0]);
        return 2;
    }
    setvbuf(stdout, NULL, _IOLBF, 0);
    char *connector_end, *uid_end, *gid_end;
    unsigned long connector = strtoul(argv[2], &connector_end, 10);
    unsigned long uid = strtoul(argv[4], &uid_end, 10);
    unsigned long gid = strtoul(argv[5], &gid_end, 10);
    if(*connector_end || !connector || connector > UINT32_MAX || *uid_end || *gid_end || uid == 0 || gid == 0 || uid >= (uid_t)-1 || gid >= (gid_t)-1)
        return 2;
    char *fd_end;
    long control_fd = strtol(argv[10], &fd_end, 10);
    if(*fd_end || control_fd < 3 || control_fd > 65535 ||
       (strcmp(argv[11], "input") != 0 && strcmp(argv[11], "start") != 0 && strcmp(argv[11], "unlock") != 0)) return 2;
    struct pointer_stream pointer = {0};
    if(!parse_coefficient(argv[6], 0.95, 1.05, &pointer.x_gain) ||
       !parse_coefficient(argv[7], -120, 120, &pointer.x_offset) ||
       !parse_coefficient(argv[8], 0.95, 1.05, &pointer.y_gain) ||
       !parse_coefficient(argv[9], -120, 120, &pointer.y_offset)) {
        fputs("Invalid touch calibration coefficients\n", stderr);
        return 2;
    }
    pointer.fd = open(argv[3], O_RDONLY | O_NONBLOCK | O_CLOEXEC);
    char name[64] = {0};
    if(pointer.fd < 0 || ioctl(pointer.fd, EVIOCGNAME(sizeof(name) - 1), name) < 0 ||
       strcmp(name, "stmfts") != 0 ||
       ioctl(pointer.fd, EVIOCGABS(ABS_X), &pointer.x) < 0 ||
       ioctl(pointer.fd, EVIOCGABS(ABS_Y), &pointer.y) < 0 ||
       pointer.x.minimum >= pointer.x.maximum || pointer.y.minimum >= pointer.y.maximum) {
        fprintf(stderr, "Expected stmfts touchscreen with valid primary pointer axes\n");
        return 1;
    }

    signal(SIGINT, stop_on_signal);
    signal(SIGTERM, stop_on_signal);
    lv_init();
    lv_tick_set_cb(ticks);
    lv_display_t *display = lv_display_create(1440, 2880);
    if(!display) return 1;
    struct kms *kms = kms_open(display, argv[1], (uint32_t)connector);
    if(!kms) return 1;
    lv_indev_t *touch = lv_indev_create();
    if(!touch) return 1;
    lv_indev_set_type(touch, LV_INDEV_TYPE_POINTER);
    lv_indev_set_display(touch, display);
    lv_indev_set_driver_data(touch, &pointer);
    lv_indev_set_read_cb(touch, read_pointer);
    if(geteuid() == 0 && (setgroups(0, NULL) || setgid((gid_t)gid) || setuid((uid_t)uid))) {
        perror("Drop panel privileges");
        return 1;
    }
    if(geteuid() != uid || getegid() != gid || prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) ||
       prctl(PR_SET_DUMPABLE, 0, 0, 0, 0)) return 1;

    printf("touch_profile x_gain=%.9f x_offset=%.6f y_gain=%.9f y_offset=%.6f\n",
           pointer.x_gain, pointer.x_offset, pointer.y_gain, pointer.y_offset);
    int direction = sensor_direction();
    if(direction >= 0) lv_display_set_rotation(display, rotations[direction]);
    panel_ui_start(display, (int)control_fd, argv[11], return_to_console);
    lv_refr_now(display);
    if(kms_presented(kms)) {
        struct timespec ready;
        clock_gettime(CLOCK_MONOTONIC, &ready);
        printf("panel_ready=1 uid=%lu monotonic_ms=%lld\n", uid,
               (long long)ready.tv_sec * 1000 + ready.tv_nsec / 1000000);
    }
    uint32_t direction_poll = lv_tick_get();
    while(!stopped && !kms_failed(kms) && kms_presented(kms)) {
        uint32_t delay = lv_timer_handler();
        if(!stopped && lv_tick_elaps(direction_poll) >= 160) {
            direction_poll = lv_tick_get();
            int next = sensor_direction();
            if(next >= 0 && next != direction && !pointer.pressed && !pointer.dropped &&
               lv_indev_get_state(touch) == LV_INDEV_STATE_RELEASED &&
               panel_ui_rotate(rotations[next], touch)) {
                direction = next;
                lv_refr_now(display);
            }
        }
        if(delay < 1) delay = 1;
        if(delay > 20) delay = 20;
        usleep(delay * 1000);
    }
    bool succeeded = kms_presented(kms) && !kms_failed(kms);
    lv_deinit();
    close(pointer.fd);
    bool restored = kms_close(kms);
    return succeeded && restored ? 0 : 1;
}
