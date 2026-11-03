/* Emulate the KMS ioctl/event contract while LVGL draws into real mapped buffers. */
#define _GNU_SOURCE
#include <drm/drm.h>
#include <drm/drm_fourcc.h>
#include <errno.h>
#include <linux/input.h>
#include <poll.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <sys/syscall.h>
#include <unistd.h>

enum { WIDTH = 1440, HEIGHT = 2880, PITCH = 5888, SIZE = PITCH * HEIGHT };
static int card = -1;
static unsigned handles;
static unsigned sequence;
static unsigned current = 80;
static int atomic_enabled, active = 1, tested;
static struct drm_event_vblank pending;

int fixture_poll(struct pollfd *fds, nfds_t count, int timeout) __asm__("poll");

int fixture_poll(struct pollfd *fds, nfds_t count, int timeout)
{
    if(count != 1 || fds[0].fd != card) return syscall(SYS_ppoll, fds, count,
        &(struct timespec){timeout / 1000, (timeout % 1000) * 1000000L}, NULL, 0);
    if(getenv("KMS_FIXTURE_DROP_EVENT") && current != 80) return 0;
    if(!pending.base.type) return 0;
    fds[0].revents = POLLIN;
    return 1;
}

ssize_t read(int fd, void *data, size_t length)
{
    if(fd != card) return syscall(SYS_read, fd, data, length);
    if(!pending.base.type || length < sizeof(pending)) {
        errno = EAGAIN;
        return -1;
    }
    memcpy(data, &pending, sizeof(pending));
    pending.base.type = 0;
    return sizeof(pending);
}

int ioctl(int fd, unsigned long request, ...)
{
    if(request == DRM_IOCTL_SET_MASTER) {
        card = fd;
        return 0;
    }
    va_list arguments;
    va_start(arguments, request);
    void *out = va_arg(arguments, void *);
    va_end(arguments);
    if(fd == card) {
        switch(request) {
        case DRM_IOCTL_SET_CLIENT_CAP: {
            const struct drm_set_client_cap *cap = out;
            if(cap->capability != DRM_CLIENT_CAP_ATOMIC || cap->value != 1) break;
            atomic_enabled = 1;
            return 0;
        }
        case DRM_IOCTL_MODE_GETPLANERESOURCES: {
            struct drm_mode_get_plane_res *r = out;
            if(!atomic_enabled || r->count_planes < 1) break;
            *(uint32_t *)(uintptr_t)r->plane_id_ptr = 99;
            r->count_planes = 1;
            return 0;
        }
        case DRM_IOCTL_MODE_GETPLANE: {
            struct drm_mode_get_plane *p = out;
            if(p->plane_id != 99) break;
            p->crtc_id = 79;
            p->fb_id = current;
            return 0;
        }
        case DRM_IOCTL_MODE_OBJ_GETPROPERTIES: {
            struct drm_mode_obj_get_properties *r = out;
            uint32_t *ids = (uint32_t *)(uintptr_t)r->props_ptr;
            uint64_t *values = (uint64_t *)(uintptr_t)r->prop_values_ptr;
            if(r->count_props < 11) break;
            if(r->obj_id == 77 && r->obj_type == DRM_MODE_OBJECT_CONNECTOR) {
                r->count_props = 1;
                ids[0] = 1;
                values[0] = 79;
            } else if(r->obj_id == 79 && r->obj_type == DRM_MODE_OBJECT_CRTC) {
                r->count_props = 2;
                ids[0] = 2;
                ids[1] = 3;
                values[0] = 20;
                values[1] = getenv("KMS_FIXTURE_INACTIVE") ? 0 : active;
            } else if(r->obj_id == 99 && r->obj_type == DRM_MODE_OBJECT_PLANE) {
                const uint64_t plane[] = {current, 79, 0, 0, WIDTH << 16, HEIGHT << 16, 0, 0, WIDTH, HEIGHT, 1};
                r->count_props = 11;
                for(uint32_t i = 0; i < r->count_props; i++) ids[i] = i + 4;
                memcpy(values, plane, sizeof(plane));
            } else break;
            return 0;
        }
        case DRM_IOCTL_MODE_GETPROPERTY: {
            struct drm_mode_get_property *r = out;
            const char *names[] = {NULL, "CRTC_ID", "MODE_ID", "ACTIVE", "FB_ID", "CRTC_ID",
                                  "SRC_X", "SRC_Y", "SRC_W", "SRC_H", "CRTC_X", "CRTC_Y",
                                  "CRTC_W", "CRTC_H", "type"};
            if(!r->prop_id || r->prop_id >= sizeof(names) / sizeof(names[0])) break;
            strcpy(r->name, names[r->prop_id]);
            return 0;
        }
        case DRM_IOCTL_MODE_GETCONNECTOR: {
            struct drm_mode_get_connector *c = out;
            if(c->connector_id != 77 || !c->count_modes) break;
            c->connector_type = DRM_MODE_CONNECTOR_DSI;
            c->connection = 1;
            c->encoder_id = 78;
            return 0;
        }
        case DRM_IOCTL_MODE_GETENCODER: {
            struct drm_mode_get_encoder *e = out;
            if(e->encoder_id != 78) break;
            e->crtc_id = 79;
            return 0;
        }
        case DRM_IOCTL_MODE_GETCRTC: {
            struct drm_mode_crtc *c = out;
            if(c->crtc_id != 79) break;
            c->fb_id = current;
            c->mode_valid = 1;
            c->mode.hdisplay = WIDTH;
            c->mode.vdisplay = HEIGHT;
            return 0;
        }
        case DRM_IOCTL_MODE_GETFB2: {
            struct drm_mode_fb_cmd2 *f = out;
            if(f->fb_id != 80) break;
            f->width = WIDTH;
            f->height = HEIGHT;
            f->pixel_format = DRM_FORMAT_XRGB8888;
            return 0;
        }
        case DRM_IOCTL_MODE_CREATE_DUMB: {
            struct drm_mode_create_dumb *b = out;
            if(b->width != WIDTH || b->height != HEIGHT || b->bpp != 32 || handles >= 2) break;
            b->handle = ++handles;
            b->pitch = PITCH;
            b->size = SIZE;
            return 0;
        }
        case DRM_IOCTL_MODE_ADDFB2: {
            struct drm_mode_fb_cmd2 *f = out;
            if(f->width != WIDTH || f->height != HEIGHT ||
               f->pitches[0] != PITCH || f->pixel_format != DRM_FORMAT_XRGB8888 ||
               f->handles[0] < 1 || f->handles[0] > 2) break;
            f->fb_id = 100 + f->handles[0];
            return 0;
        }
        case DRM_IOCTL_MODE_MAP_DUMB: {
            struct drm_mode_map_dumb *m = out;
            if(m->handle < 1 || m->handle > 2) break;
            m->offset = (m->handle - 1) * SIZE;
            return 0;
        }
        case DRM_IOCTL_MODE_ATOMIC: {
            const struct drm_mode_atomic *r = out;
            const uint32_t *objects = (const uint32_t *)(uintptr_t)r->objs_ptr;
            const uint32_t *counts = (const uint32_t *)(uintptr_t)r->count_props_ptr;
            const uint32_t *ids = (const uint32_t *)(uintptr_t)r->props_ptr;
            const uint64_t *values = (const uint64_t *)(uintptr_t)r->prop_values_ptr;
            const unsigned commit = DRM_MODE_PAGE_FLIP_EVENT | DRM_MODE_ATOMIC_NONBLOCK;
            if(!atomic_enabled || objects[0] != 99 || ids[0] != 4) break;
            if(values[0] != 80 && values[0] != 101 && values[0] != 102) break;
            if(values[0] == current) break;
            if(r->count_objs == 3) {
                const uint32_t expected_ids[] = {4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 1, 2, 3};
                const uint64_t expected_values[] = {79, 0, 0, WIDTH << 16, HEIGHT << 16, 0, 0, WIDTH, HEIGHT, 79, 20, 1};
                if(counts[0] != 10 || counts[1] != 1 || counts[2] != 2 ||
                   objects[1] != 77 || objects[2] != 79 ||
                   memcmp(ids, expected_ids, sizeof(expected_ids)) ||
                   memcmp(values + 1, expected_values, sizeof(expected_values))) break;
                if(r->flags == (DRM_MODE_ATOMIC_TEST_ONLY | DRM_MODE_ATOMIC_ALLOW_MODESET)) {
                    if(getenv("KMS_FIXTURE_FAIL_TEST")) break;
                    tested = 1;
                    return 0;
                }
                if(!tested || r->flags != (commit | DRM_MODE_ATOMIC_ALLOW_MODESET)) break;
                active = 1;
            } else if(r->count_objs != 1 || counts[0] != 1 || !active || r->flags != commit) break;
            current = (unsigned)values[0];
            pending = (struct drm_event_vblank){
                .base = {DRM_EVENT_FLIP_COMPLETE, sizeof(pending)},
                .user_data = r->user_data, .sequence = ++sequence, .crtc_id = 79,
            };
            return 0;
        }
        }
        errno = EINVAL;
        return -1;
    }
    if(request == EVIOCGNAME(63)) {
        memcpy(out, "stmfts", sizeof("stmfts"));
        return sizeof("stmfts");
    }
    if(request == EVIOCGABS(ABS_MT_POSITION_X) || request == EVIOCGABS(ABS_X)) {
        *(struct input_absinfo *)out = (struct input_absinfo){.minimum = 10, .maximum = 1449};
        return 0;
    }
    if(request == EVIOCGABS(ABS_MT_POSITION_Y) || request == EVIOCGABS(ABS_Y)) {
        *(struct input_absinfo *)out = (struct input_absinfo){.minimum = 20, .maximum = 2899};
        return 0;
    }
    errno = ENOTTY;
    return -1;
}
