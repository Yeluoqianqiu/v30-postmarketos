#ifndef V30_LVGL_KMS_H
#define V30_LVGL_KMS_H

#include "lvgl.h"
#include <stdint.h>

struct kms;

struct kms *kms_open(lv_display_t *display, const char *path, uint32_t connector_id);
bool kms_presented(const struct kms *kms);
bool kms_failed(const struct kms *kms);
bool kms_close(struct kms *kms);

#endif
