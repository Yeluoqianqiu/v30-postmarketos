#include "kms.h"
#include "ui.h"

#include <drm/drm.h>
#include <drm/drm_fourcc.h>
#include <errno.h>
#include <fcntl.h>
#include <poll.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <time.h>
#include <unistd.h>

enum { WIDTH = 1440, HEIGHT = 2880, PIXEL_BYTES = 4, TILE_BYTES = 1024 * 1024 };
enum { FB_ID, PLANE_CRTC, SRC_X, SRC_Y, SRC_W, SRC_H, CRTC_X, CRTC_Y, CRTC_W, CRTC_H, PLANE_TYPE };

struct property {
    const char *name;
    uint32_t id;
    uint64_t value;
};

struct buffer {
    uint32_t id;
    uint32_t pitch;
    size_t size;
    unsigned char *pixels;
};

struct kms {
    int fd;
    uint32_t connector;
    uint32_t crtc;
    uint32_t plane;
    uint32_t original_fb;
    struct property connector_crtc;
    struct property crtc_props[2];
    struct property plane_props[PLANE_TYPE + 1];
    struct buffer buffers[2];
    unsigned front;
    unsigned char *draw;
    unsigned char *rotated;
    lv_area_t damage;
    bool dirty;
    bool submitted;
    bool failed;
    uint64_t request;
    unsigned presented;
};

static int64_t monotonic_ms(void)
{
    struct timespec now;
    clock_gettime(CLOCK_MONOTONIC, &now);
    return (int64_t)now.tv_sec * 1000 + now.tv_nsec / 1000000;
}

static bool get_dsi_crtc(struct kms *kms, uint32_t connector_id)
{
    struct drm_mode_modeinfo cached_mode;
    struct drm_mode_get_connector connector = {
        .connector_id = connector_id, .count_modes = 1,
        .modes_ptr = (uintptr_t)&cached_mode,
    };
    if(ioctl(kms->fd, DRM_IOCTL_MODE_GETCONNECTOR, &connector) < 0) return false;
    if(connector.connector_type != DRM_MODE_CONNECTOR_DSI ||
       connector.connection != 1 || !connector.encoder_id) {
        errno = ENODEV;
        return false;
    }

    struct drm_mode_get_encoder encoder = {.encoder_id = connector.encoder_id};
    if(ioctl(kms->fd, DRM_IOCTL_MODE_GETENCODER, &encoder) < 0) return false;
    struct drm_mode_crtc crtc = {.crtc_id = encoder.crtc_id};
    if(!crtc.crtc_id) {
        errno = ENODEV;
        return false;
    }
    if(ioctl(kms->fd, DRM_IOCTL_MODE_GETCRTC, &crtc) < 0) return false;
    if(!crtc.mode_valid || !crtc.fb_id || crtc.x || crtc.y ||
       crtc.mode.hdisplay != WIDTH || crtc.mode.vdisplay != HEIGHT) {
        errno = ENOTSUP;
        return false;
    }
    struct drm_mode_fb_cmd2 fb = {.fb_id = crtc.fb_id};
    if(ioctl(kms->fd, DRM_IOCTL_MODE_GETFB2, &fb) < 0) return false;
    if(fb.pixel_format != DRM_FORMAT_XRGB8888 || fb.width != WIDTH || fb.height != HEIGHT) {
        errno = ENOTSUP;
        return false;
    }
    kms->crtc = crtc.crtc_id;
    kms->connector = connector_id;
    kms->original_fb = crtc.fb_id;
    printf("kms_output=DSI connector=%u crtc=%u mode=%dx%d original_fb=%u\n",
           connector_id, kms->crtc, WIDTH, HEIGHT, kms->original_fb);
    return true;
}

static bool get_properties(int fd, uint32_t object, uint32_t type,
                           struct property *properties, size_t count)
{
    uint32_t ids[64];
    uint64_t values[64];
    struct drm_mode_obj_get_properties req = {
        .obj_id = object, .obj_type = type, .count_props = 64,
        .props_ptr = (uintptr_t)ids, .prop_values_ptr = (uintptr_t)values,
    };
    if(ioctl(fd, DRM_IOCTL_MODE_OBJ_GETPROPERTIES, &req) < 0) return false;
    if(req.count_props > 64) {
        errno = EOVERFLOW;
        return false;
    }
    for(uint32_t i = 0; i < req.count_props; i++) {
        struct drm_mode_get_property prop = {.prop_id = ids[i]};
        if(ioctl(fd, DRM_IOCTL_MODE_GETPROPERTY, &prop) < 0) return false;
        for(size_t j = 0; j < count; j++) {
            if(strncmp(prop.name, properties[j].name, sizeof(prop.name)) != 0) continue;
            properties[j].id = ids[i];
            properties[j].value = values[i];
            break;
        }
    }
    for(size_t i = 0; i < count; i++) {
        if(properties[i].id) continue;
        fprintf(stderr, "Missing KMS property %s on object %u\n", properties[i].name, object);
        errno = ENOENT;
        return false;
    }
    return true;
}

static bool prepare_atomic(struct kms *kms)
{
    uint32_t planes[64];
    struct drm_mode_get_plane_res list = {.count_planes = 64, .plane_id_ptr = (uintptr_t)planes};
    if(ioctl(kms->fd, DRM_IOCTL_MODE_GETPLANERESOURCES, &list) < 0) return false;
    if(list.count_planes > 64) {
        errno = EOVERFLOW;
        return false;
    }
    for(uint32_t i = 0; i < list.count_planes; i++) {
        struct drm_mode_get_plane plane = {.plane_id = planes[i]};
        if(ioctl(kms->fd, DRM_IOCTL_MODE_GETPLANE, &plane) < 0) return false;
        if(plane.crtc_id != kms->crtc || plane.fb_id != kms->original_fb) continue;
        struct property props[] = {
            [FB_ID] = {.name = "FB_ID"}, [PLANE_CRTC] = {.name = "CRTC_ID"},
            [SRC_X] = {.name = "SRC_X"}, [SRC_Y] = {.name = "SRC_Y"},
            [SRC_W] = {.name = "SRC_W"}, [SRC_H] = {.name = "SRC_H"},
            [CRTC_X] = {.name = "CRTC_X"}, [CRTC_Y] = {.name = "CRTC_Y"},
            [CRTC_W] = {.name = "CRTC_W"}, [CRTC_H] = {.name = "CRTC_H"},
            [PLANE_TYPE] = {.name = "type"},
        };
        if(!get_properties(kms->fd, plane.plane_id, DRM_MODE_OBJECT_PLANE,
                           props, PLANE_TYPE + 1)) return false;
        if(props[PLANE_TYPE].value != 1) continue; /* DRM_PLANE_TYPE_PRIMARY */
        memcpy(kms->plane_props, props, sizeof(props));
        kms->plane = plane.plane_id;
        break;
    }
    if(!kms->plane) {
        errno = ENODEV;
        return false;
    }

    kms->connector_crtc.name = "CRTC_ID";
    kms->crtc_props[0].name = "MODE_ID";
    kms->crtc_props[1].name = "ACTIVE";
    if(!get_properties(kms->fd, kms->connector, DRM_MODE_OBJECT_CONNECTOR, &kms->connector_crtc, 1) ||
       !get_properties(kms->fd, kms->crtc, DRM_MODE_OBJECT_CRTC, kms->crtc_props, 2)) return false;
    if(kms->connector_crtc.value != kms->crtc || !kms->crtc_props[0].value ||
       kms->plane_props[FB_ID].value != kms->original_fb || kms->plane_props[PLANE_CRTC].value != kms->crtc) {
        errno = ENOTSUP;
        return false;
    }
    printf("kms_atomic_snapshot plane=%u mode_blob=%llu active=%llu\n", kms->plane,
           (unsigned long long)kms->crtc_props[0].value, (unsigned long long)kms->crtc_props[1].value);
    if(kms->crtc_props[1].value != 1) {
        fputs("DSI inactive after tty1 wake\n", stderr);
        errno = EAGAIN;
        return false;
    }
    return true;
}

static bool allocate_buffer(int fd, struct buffer *buffer)
{
    struct drm_mode_create_dumb create = {.width = WIDTH, .height = HEIGHT, .bpp = 32};
    if(ioctl(fd, DRM_IOCTL_MODE_CREATE_DUMB, &create) < 0) return false;
    if(create.pitch < WIDTH * PIXEL_BYTES ||
       create.size < (uint64_t)create.pitch * HEIGHT || create.size > 32u * 1024u * 1024u) {
        errno = EOVERFLOW;
        return false;
    }

    struct drm_mode_fb_cmd2 fb = {
        .width = WIDTH, .height = HEIGHT, .pixel_format = DRM_FORMAT_XRGB8888,
        .handles = {create.handle}, .pitches = {create.pitch},
    };
    if(ioctl(fd, DRM_IOCTL_MODE_ADDFB2, &fb) < 0) return false;
    struct drm_mode_map_dumb map = {.handle = create.handle};
    if(ioctl(fd, DRM_IOCTL_MODE_MAP_DUMB, &map) < 0) return false;
    void *pixels = mmap(NULL, create.size, PROT_READ | PROT_WRITE, MAP_SHARED, fd, map.offset);
    if(pixels == MAP_FAILED) return false;
    *buffer = (struct buffer){fb.fb_id, create.pitch, create.size, pixels};
    return true;
}

static bool flip(struct kms *kms, uint32_t fb, bool restore)
{
    const bool initial = !kms->submitted && !restore;
    uint32_t objects[] = {kms->plane, kms->connector, kms->crtc};
    uint32_t counts[] = {initial ? PLANE_TYPE : 1, 1, 2};
    uint32_t properties[PLANE_TYPE + 3];
    uint64_t values[PLANE_TYPE + 3];
    for(size_t i = 0; i < PLANE_TYPE; i++) {
        properties[i] = kms->plane_props[i].id;
        values[i] = kms->plane_props[i].value;
    }
    values[FB_ID] = fb;
    properties[PLANE_TYPE] = kms->connector_crtc.id;
    values[PLANE_TYPE] = kms->crtc;
    properties[PLANE_TYPE + 1] = kms->crtc_props[0].id;
    values[PLANE_TYPE + 1] = kms->crtc_props[0].value;
    properties[PLANE_TYPE + 2] = kms->crtc_props[1].id;
    values[PLANE_TYPE + 2] = 1;
    struct drm_mode_atomic request = {
        .count_objs = initial ? 3 : 1,
        .objs_ptr = (uintptr_t)objects, .count_props_ptr = (uintptr_t)counts,
        .props_ptr = (uintptr_t)properties, .prop_values_ptr = (uintptr_t)values,
    };
    if(initial) {
        request.flags = DRM_MODE_ATOMIC_TEST_ONLY | DRM_MODE_ATOMIC_ALLOW_MODESET;
        if(ioctl(kms->fd, DRM_IOCTL_MODE_ATOMIC, &request) < 0) {
            perror("DSI atomic TEST_ONLY");
            return false;
        }
        puts("kms_atomic_test_only=passed");
    }
    request.flags = DRM_MODE_PAGE_FLIP_EVENT | DRM_MODE_ATOMIC_NONBLOCK;
    if(initial) request.flags |= DRM_MODE_ATOMIC_ALLOW_MODESET;
    request.user_data = ++kms->request;
    if(ioctl(kms->fd, DRM_IOCTL_MODE_ATOMIC, &request) < 0) return false;
    if(!restore) kms->submitted = true;

    int64_t deadline = monotonic_ms() + 750;
    while(monotonic_ms() < deadline) {
        struct pollfd ready = {.fd = kms->fd, .events = POLLIN};
        int left = (int)(deadline - monotonic_ms());
        int status = poll(&ready, 1, left > 0 ? left : 0);
        if(status < 0 && errno == EINTR) continue;
        if(status < 0) return false;
        if(status == 0) break;
        if(!(ready.revents & POLLIN)) {
            errno = EIO;
            return false;
        }
        struct drm_event_vblank event;
        ssize_t length = read(kms->fd, &event, sizeof(event));
        if(length < 0 && (errno == EINTR || errno == EAGAIN)) continue;
        if(length != sizeof(event) || event.base.length != sizeof(event) ||
           event.base.type != DRM_EVENT_FLIP_COMPLETE || event.crtc_id != kms->crtc) {
            errno = EPROTO;
            return false;
        }
        if(event.user_data != request.user_data) continue;
        if(!restore) {
            kms->presented++;
            panel_ui_frame_presented();
        }
        if(restore || kms->presented == 1)
            printf("%s_flip_complete sequence=%u crtc=%u fb=%u\n",
                   restore ? "tty" : "panel", event.sequence, event.crtc_id, fb);
        return true;
    }
    errno = ETIMEDOUT;
    return false;
}

static void flush(lv_display_t *display, const lv_area_t *area, uint8_t *pixels)
{
    struct kms *kms = lv_display_get_driver_data(display);
    if(kms->failed) goto ready;

    lv_area_t physical = *area;
    lv_display_rotate_area(display, &physical);
    int32_t width = lv_area_get_width(area);
    int32_t height = lv_area_get_height(area);
    uint32_t src_stride = lv_draw_buf_width_to_stride(width, LV_COLOR_FORMAT_XRGB8888);
    lv_display_rotation_t rotation = lv_display_get_rotation(display);
    uint32_t dst_stride = lv_draw_buf_width_to_stride(lv_area_get_width(&physical), LV_COLOR_FORMAT_XRGB8888);
    if(physical.x1 < 0 || physical.y1 < 0 || physical.x2 >= WIDTH || physical.y2 >= HEIGHT ||
       (size_t)dst_stride * lv_area_get_height(&physical) > TILE_BYTES) {
        fputs("Unexpected LVGL flush bounds\n", stderr);
        kms->failed = true;
        goto ready;
    }
    if(rotation != LV_DISPLAY_ROTATION_0) {
        lv_draw_sw_rotate(pixels, kms->rotated, width, height, src_stride, dst_stride,
                          rotation, LV_COLOR_FORMAT_XRGB8888);
        pixels = kms->rotated;
    } else {
        dst_stride = src_stride;
    }

    struct buffer *back = &kms->buffers[1 - kms->front];
    size_t x = (size_t)physical.x1 * PIXEL_BYTES;
    size_t span = (size_t)lv_area_get_width(&physical) * PIXEL_BYTES;
    for(int32_t row = physical.y1; row <= physical.y2; row++)
        memcpy(back->pixels + (size_t)row * back->pitch + x,
               pixels + (size_t)(row - physical.y1) * dst_stride, span);
    if(kms->dirty) {
        kms->damage.x1 = LV_MIN(kms->damage.x1, physical.x1);
        kms->damage.y1 = LV_MIN(kms->damage.y1, physical.y1);
        kms->damage.x2 = LV_MAX(kms->damage.x2, physical.x2);
        kms->damage.y2 = LV_MAX(kms->damage.y2, physical.y2);
    }
    else {
        kms->damage = physical;
        kms->dirty = true;
    }

    if(lv_display_flush_is_last(display)) {
        if(!flip(kms, back->id, false)) {
            perror("DSI page flip");
            kms->failed = true;
            goto ready;
        }

        /* Update the retired buffer only after the new buffer is on screen. */
        struct buffer *retired = &kms->buffers[kms->front];
        x = (size_t)kms->damage.x1 * PIXEL_BYTES;
        span = (size_t)lv_area_get_width(&kms->damage) * PIXEL_BYTES;
        for(int32_t row = kms->damage.y1; row <= kms->damage.y2; row++)
            memcpy(retired->pixels + (size_t)row * retired->pitch + x,
                   back->pixels + (size_t)row * back->pitch + x, span);
        kms->front = 1 - kms->front;
        kms->dirty = false;
    }
ready:
    lv_display_flush_ready(display);
}

struct kms *kms_open(lv_display_t *display, const char *path, uint32_t connector_id)
{
    struct kms *kms = calloc(1, sizeof(*kms));
    if(!kms) return NULL;
    kms->fd = open(path, O_RDWR | O_CLOEXEC | O_NONBLOCK);
    struct drm_set_client_cap atomic = {.capability = DRM_CLIENT_CAP_ATOMIC, .value = 1};
    if(kms->fd < 0 || ioctl(kms->fd, DRM_IOCTL_SET_MASTER, 0) < 0 ||
       ioctl(kms->fd, DRM_IOCTL_SET_CLIENT_CAP, &atomic) < 0 ||
       !get_dsi_crtc(kms, connector_id) || !prepare_atomic(kms) ||
       !allocate_buffer(kms->fd, &kms->buffers[0]) ||
       !allocate_buffer(kms->fd, &kms->buffers[1])) {
        perror("Prepare DSI KMS");
        kms_close(kms);
        return NULL;
    }
    kms->draw = malloc(TILE_BYTES);
    kms->rotated = malloc(TILE_BYTES);
    if(!kms->draw || !kms->rotated) {
        perror("Allocate LVGL tiles");
        kms_close(kms);
        return NULL;
    }

    lv_display_set_driver_data(display, kms);
    lv_display_set_color_format(display, LV_COLOR_FORMAT_XRGB8888);
    lv_display_set_rotation(display, LV_DISPLAY_ROTATION_270);
    lv_display_set_buffers(display, kms->draw, NULL, TILE_BYTES, LV_DISPLAY_RENDER_MODE_PARTIAL);
    lv_display_set_flush_cb(display, flush);
    return kms;
}

bool kms_presented(const struct kms *kms)
{
    return kms->presented > 0;
}

bool kms_failed(const struct kms *kms)
{
    return kms->failed;
}

bool kms_close(struct kms *kms)
{
    bool restored = true;
    if(kms->submitted && !flip(kms, kms->original_fb, true)) {
        perror("Restore original KMS framebuffer");
        restored = false;
    }
    for(size_t i = 0; i < 2; i++) {
        struct buffer *buffer = &kms->buffers[i];
        if(buffer->pixels) munmap(buffer->pixels, buffer->size);
    }
    /* Closing the DRM fd releases our FB/GEM resources and restores fbdev. */
    if(kms->fd >= 0) close(kms->fd);
    free(kms->rotated);
    free(kms->draw);
    free(kms);
    return restored;
}
