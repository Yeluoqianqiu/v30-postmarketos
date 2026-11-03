#ifndef V30_PANEL_UI_H
#define V30_PANEL_UI_H

#include "lvgl.h"

void panel_ui_start(lv_display_t *display, int socket_fd, const char *mode, void (*leave)(void));
bool panel_ui_rotate(lv_display_rotation_t rotation, lv_indev_t *touch);
void panel_ui_frame_presented(void);

#endif
