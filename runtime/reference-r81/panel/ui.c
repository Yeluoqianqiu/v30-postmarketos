#include "ui.h"

#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <time.h>
#include <unistd.h>

#ifndef V30_PANEL_FONT_PATH
#define V30_PANEL_FONT_PATH "/usr/share/fonts/noto/NotoSansCJK-Regular.ttc"
#endif

enum page { NETWORK, WIFI, PHONE, MISSED, SMS, AUDIO, TEXT, TERMINAL, BLUETOOTH, MOBILE, MEDIA };
enum response { NONE, STATUS, LIST, CALL_LOG, CALLBACK_NUMBER, SMS_LIST, SMS_BODY, LEVELS,
                TEXT_DONE, PINYIN_CANDIDATES, OVERVIEW, DETAIL_BODY, UNLOCKED, MEDIA_STATE,
                TERM_OPEN, TERM_POLL, TERM_KEY, TERM_INPUT };

static struct {
    int socket_fd;
    enum response pending;
    lv_obj_t *screen, *body, *status, *list, *entry, *detail, *dial, *speaker, *ring;
    lv_obj_t *typing_keys, *ime_switch, *composition, *candidates[6];
    lv_obj_t *term_scroll, *term_output, *term_keyboard_button, *term_send_button;
    lv_obj_t *term_cursor, *term_bottom;
    lv_display_t *display;
    lv_obj_t *tabs[4], *home_switch[3], *tile_state[3], *home_notice[2], *overview_notice[2];
    lv_obj_t *shade, *shade_content, *brightness, *clock, *signals, *system_icons, *notice_icons;
    lv_obj_t *bar, *mic, *media_info, *media_record, *media_play, *media_stop, *torch;
    lv_obj_t *hero_clock, *hero_date, *home_wifi, *notice_hint, *shade_hint, *shade_handle_label;
    lv_obj_t *brightness_value, *media_clock, *shade_backdrop;
    const lv_font_t *hero_font;
    int body_height, shade_level, shade_compact_height;
    bool portrait, panel_unlocked, status_refresh, rotating;
    bool rotation_flip_pending, input_only, sms_body, sms_unread;
    enum page page;
    int home_network[3];
    lv_font_t *term_font;
    const char *queued_key, *sent_key;
    unsigned queued_submit;
    uint32_t term_last_poll;
    bool term_open, term_keyboard, term_enter, term_utf8, term_follow, term_scrolling;
    bool list_ready, recording, playing, media_refresh, media_stop_queued;
    uint32_t media_last_poll, media_start;
    bool chinese;
    bool hardware_key;
    bool home_flip_pending;
    bool home_status_pending;
    char lookup[25];
    char dial_number[22];
    void (*leave)(void);
} ui;

static void show_page(enum page page);
static void add_tabs(void);
static void show_records(const char *body, bool missed);
static void show_message(const char *body);
static void show_candidates(const char *body);
static void terminal_reply(enum response kind, bool success, const char *body);
static void submit_terminal(bool enter);
static void overview_reply(const char *body);
static void media_reply(const char *body);
static void tab(lv_event_t *event);
static void build_screen(void);
static void set_shade(int level);
static void show_unlock(void);

static bool is_portrait(lv_display_rotation_t rotation)
{
    return rotation == LV_DISPLAY_ROTATION_0 || rotation == LV_DISPLAY_ROTATION_180;
}

static int sx(int value)
{
    return ui.portrait ? value / 2 : value;
}

static void select_tab(unsigned selected)
{
    for(unsigned i = 0; i < 4; ++i)
        if(ui.tabs[i]) lv_obj_set_style_bg_color(ui.tabs[i], lv_color_hex(i == selected ? 0x203e37 : 0x151e24), 0);
}

static void mark_time(const char *name)
{
    struct timespec now;
    clock_gettime(CLOCK_MONOTONIC, &now);
    printf("%s=%lld\n", name, (long long)now.tv_sec * 1000 + now.tv_nsec / 1000000);
}

void panel_ui_frame_presented(void)
{
    if(ui.rotation_flip_pending) {
        ui.rotation_flip_pending = false;
        printf("panel_orientation_flip=%d\n", lv_display_get_rotation(ui.display));
    }
    if(ui.home_flip_pending) {
        ui.home_flip_pending = false;
        mark_time("panel_home_flip_ms");
    }
}

static const char *tr(const char *chinese, const char *english)
{
    return ui.chinese ? chinese : english;
}

static lv_obj_t *label(lv_obj_t *parent, const char *text, int x, int y)
{
    lv_obj_t *obj = lv_label_create(parent);
    lv_label_set_text(obj, text);
    lv_obj_set_pos(obj, sx(x), y);
    return obj;
}

static lv_obj_t *button(lv_obj_t *parent, const char *text, int x, int y, int width,
                       lv_event_cb_t callback, void *argument)
{
    lv_obj_t *obj = lv_button_create(parent);
    lv_obj_set_pos(obj, sx(x), y);
    lv_obj_set_size(obj, sx(width), 112);
    lv_obj_set_style_radius(obj, 34, 0);
    lv_obj_set_style_bg_color(obj, lv_color_hex(0x30454e), LV_STATE_PRESSED);
    lv_obj_set_style_bg_color(obj, lv_color_hex(0x152028), LV_STATE_DISABLED);
    lv_obj_set_style_text_color(obj, lv_color_hex(0x81929d), LV_STATE_DISABLED);
    lv_obj_set_style_bg_color(obj, lv_color_hex(0x1a262f), 0);
    lv_obj_set_style_shadow_width(obj, 0, 0);
    lv_obj_set_style_text_color(obj, lv_color_hex(0xeaf0f2), 0);
    lv_obj_add_event_cb(obj, callback, LV_EVENT_CLICKED, argument);
    lv_obj_center(label(obj, text, 0, 0));
    return obj;
}

static bool send_request(enum response kind, const char *request)
{
    if(ui.pending != NONE) {
        lv_label_set_text(ui.status, tr("请等待当前操作完成", "Please wait for the current action."));
        return false;
    }
    if(send(ui.socket_fd, request, strlen(request), MSG_DONTWAIT | MSG_NOSIGNAL) < 0) {
        lv_label_set_text(ui.status, "Control service unavailable.");
        return false;
    }
    ui.pending = kind;
    if(kind < TERM_OPEN && !(kind == OVERVIEW && ui.status_refresh) && !(kind == MEDIA_STATE && ui.media_refresh))
        lv_label_set_text(ui.status, tr("处理中…", "Working..."));
    return true;
}

static void read_reply(lv_timer_t *timer)
{
    (void)timer;
    if(ui.pending == NONE) return;
    char reply[48001];
    ssize_t count = recv(ui.socket_fd, reply, sizeof(reply) - 1, MSG_DONTWAIT);
    if(count < 0 && (errno == EAGAIN || errno == EINTR)) return;
    enum response kind = ui.pending;
    ui.pending = NONE;
    if(count <= 0) {
        lv_label_set_text(ui.status, "Control service disconnected.");
        return;
    }
    reply[count] = 0;
    const char *body = reply + 1;
    if(kind == OVERVIEW) ui.status_refresh = false;
    if(kind == MEDIA_STATE) ui.media_refresh = false;
    if(kind == OVERVIEW && ui.home_status_pending) {
        ui.home_status_pending = false;
        mark_time("panel_home_controls_ms");
    }
    if(kind >= TERM_OPEN) {
        terminal_reply(kind, reply[0] == '1', body);
        return;
    }
    if(reply[0] != '1') {
        lv_label_set_text(ui.status, body);
        return;
    }
    if(kind == UNLOCKED) {
        puts("panel_unlocked=1");
        mark_time("panel_unlock_accepted_ms");
        ui.panel_unlocked = true;
        add_tabs();
        show_page(NETWORK);
        ui.home_status_pending = ui.pending == OVERVIEW;
        ui.home_flip_pending = true;
    } else if(kind == MEDIA_STATE) {
        media_reply(body);
    } else if(kind == OVERVIEW) {
        overview_reply(body);
    } else if(kind == DETAIL_BODY) {
        lv_label_set_text(ui.detail, body);
        lv_label_set_text(ui.status, "");
    } else if(kind == LIST) {
        ui.list_ready = *body != 0;
        lv_dropdown_set_options(ui.list, ui.list_ready ? body : tr("暂无条目", "No entries"));
        lv_label_set_text(ui.status, ui.list_ready ? tr("请选择一项", "Select an entry.") : tr("暂无条目", "No entries."));
    } else if(kind == CALL_LOG || kind == SMS_LIST) {
        show_records(body, kind == CALL_LOG);
    } else if(kind == CALLBACK_NUMBER) {
        show_page(PHONE);
        lv_textarea_set_text(ui.entry, body);
        lv_label_set_text(ui.status, tr("号码已填入。点「拨号」后确认。", "Number filled. Tap Dial, then confirm."));
    } else if(kind == SMS_BODY) {
        show_message(body);
    } else if(kind == PINYIN_CANDIDATES) {
        show_candidates(body);
    } else {
        lv_label_set_text(ui.status, body);
        if(kind == LEVELS) {
            int speaker, ring;
            const char *ring_text = strstr(body, "Ringtone volume: ");
            if(sscanf(body, "Speaker: %d", &speaker) == 1) {
                lv_slider_set_value(ui.speaker, speaker, LV_ANIM_OFF);
                lv_obj_send_event(ui.speaker, LV_EVENT_VALUE_CHANGED, NULL);
            }
            if(ring_text && sscanf(ring_text, "Ringtone volume: %d", &ring) == 1) {
                lv_slider_set_value(ui.ring, ring, LV_ANIM_OFF);
                lv_obj_send_event(ui.ring, LV_EVENT_VALUE_CHANGED, NULL);
            }
        }
        if(kind == TEXT_DONE) ui.leave();
    }
}

static void leave(lv_event_t *event)
{
    (void)event;
    ui.leave();
}

static void action(lv_event_t *event)
{
    const char *request = lv_event_get_user_data(event);
    send_request(STATUS, request);
}

static void network_scan(lv_event_t *event)
{
    (void)event;
    send_request(LIST, "wifi.scan");
}

static void wifi_join(lv_event_t *event)
{
    (void)event;
    if(!ui.list_ready) return;
    const char *secret = lv_textarea_get_text(ui.entry);
    if(strpbrk(secret, "\t\r\n")) return;
    char request[96];
    int len = snprintf(request, sizeof(request), "wifi.join\t%u\t%s", lv_dropdown_get_selected(ui.list), secret);
    if(len > 0 && len < (int)sizeof(request) && send_request(STATUS, request))
        lv_textarea_set_text(ui.entry, "");
    memset(request, 0, sizeof(request));
}

static void show_missed(lv_event_t *event)
{
    (void)event;
    send_request(CALL_LOG, "phone.missed");
}

static void list_messages(lv_event_t *event)
{
    bool unread = event && lv_event_get_user_data(event);
    if(send_request(SMS_LIST, unread ? "sms.list\tunread" : "sms.list"))
        ui.sms_unread = unread;
}

static void read_message(lv_event_t *event)
{
    (void)event;
    char request[32];
    snprintf(request, sizeof(request), "sms.read\t%u", (unsigned)(uintptr_t)lv_event_get_user_data(event));
    send_request(SMS_BODY, request);
}

static void select_missed(lv_event_t *event)
{
    char request[40];
    snprintf(request, sizeof(request), "phone.missed.select\t%u",
             (unsigned)(uintptr_t)lv_event_get_user_data(event));
    send_request(CALLBACK_NUMBER, request);
}

static void sms_back(lv_event_t *event)
{
    (void)event;
    ui.sms_unread = false;
    show_page(SMS);
}

static void dial_reset(lv_event_t *event)
{
    (void)event;
    ui.dial_number[0] = 0;
    lv_label_set_text(lv_obj_get_child(ui.dial, 0), tr("拨号", "Dial"));
}

static void dial(lv_event_t *event)
{
    (void)event;
    const char *number = lv_textarea_get_text(ui.entry);
    const char *digits = number + (number[0] == '+');
    size_t length = strlen(digits);
    if(length < 3 || length > 20 || digits[strspn(digits, "0123456789")]) {
        lv_label_set_text(ui.status, tr("请输入电话号码", "Enter a phone number."));
        return;
    }
    if(strcmp(number, ui.dial_number) != 0) {
        snprintf(ui.dial_number, sizeof(ui.dial_number), "%s", number);
        lv_label_set_text_fmt(ui.status, tr("拨打 %s？请点确认拨号。", "Dial %s? Tap Confirm call."), ui.dial_number);
        lv_label_set_text(lv_obj_get_child(ui.dial, 0), tr("确认拨号", "Confirm call"));
        return;
    }
    char request[40];
    snprintf(request, sizeof(request), "phone.dial\t%s", ui.dial_number);
    if(send_request(STATUS, request)) dial_reset(NULL);
}

static void volume(lv_event_t *event)
{
    const char *name = lv_event_get_user_data(event);
    lv_obj_t *slider = name[0] == 's' ? ui.speaker : ui.ring;
    char request[32];
    snprintf(request, sizeof(request), "%s\t%d", name, (int)lv_slider_get_value(slider));
    send_request(LEVELS, request);
}

static void slider_label(lv_event_t *event)
{
    lv_obj_t *caption = lv_event_get_user_data(event);
    lv_label_set_text_fmt(caption, "%d%%", (int)lv_slider_get_value(lv_event_get_target(event)));
}

static void finish_text(lv_event_t *event)
{
    (void)event;
    const char *text = lv_textarea_get_text(ui.entry);
    if(ui.composition && *lv_textarea_get_text(ui.composition)) {
        lv_label_set_text(ui.status, tr("请先选择拼音候选词。", "Choose a Pinyin candidate first."));
        return;
    }
    if(strpbrk(text, "\t\r\n")) return;
    char request[1040];
    int len = snprintf(request, sizeof(request), "%s\t%s", ui.hardware_key ? "text.paste" : "text", text);
    if(len > 0 && len < (int)sizeof(request)) send_request(TEXT_DONE, request);
}

static void unlock_panel(lv_event_t *event)
{
    (void)event;
    const char *pin = lv_textarea_get_text(ui.entry);
    if(strlen(pin) != 6 || strspn(pin, "0123456789") != 6) {
        lv_label_set_text(ui.status, tr("请输入 6 位数字。", "Enter six digits."));
        return;
    }
    char request[32];
    int len = snprintf(request, sizeof(request), "panel.unlock\t%s", pin);
    if(len > 0 && len < (int)sizeof(request) && send_request(UNLOCKED, request)) {
        mark_time("panel_unlock_submitted_ms");
        lv_textarea_set_text(ui.entry, "");
    }
    volatile char *clear = request;
    for(size_t i = 0; i < sizeof(request); i++) clear[i] = 0;
}

static lv_obj_t *entry(int x, int y, int width, unsigned maximum, const char *hint)
{
    lv_obj_t *obj = lv_textarea_create(ui.body);
    lv_obj_set_pos(obj, sx(x), y);
    lv_obj_set_size(obj, sx(width), 114);
    lv_textarea_set_one_line(obj, true);
    lv_textarea_set_max_length(obj, maximum);
    lv_textarea_set_placeholder_text(obj, hint);
    return obj;
}

static lv_obj_t *keyboard(lv_obj_t *input, int y)
{
    lv_obj_t *obj = lv_keyboard_create(ui.body);
    lv_obj_set_align(obj, LV_ALIGN_TOP_LEFT);
    lv_obj_set_pos(obj, 0, y);
    lv_obj_set_size(obj, sx(2700), 720);
    lv_obj_set_style_text_font(obj, &lv_font_montserrat_48, LV_PART_ITEMS);
    lv_keyboard_set_textarea(obj, input);
    return obj;
}

static void terminal_key(const char *key)
{
    if(!ui.term_open) return;
    if(ui.pending != NONE) {
        ui.queued_key = key;
        return;
    }
    char request[32];
    snprintf(request, sizeof(request), "term.key\t%s", key);
    if(send_request(TERM_KEY, request)) ui.sent_key = key;
}

static void terminal_follow(lv_event_t *event)
{
    (void)event;
    ui.term_follow = true;
    lv_obj_add_flag(ui.term_bottom, LV_OBJ_FLAG_HIDDEN);
    lv_obj_add_flag(ui.term_cursor, LV_OBJ_FLAG_HIDDEN);
    ui.term_scrolling = true;
    lv_obj_update_layout(ui.term_scroll);
    int bottom = lv_obj_get_scroll_bottom(ui.term_scroll);
    if(bottom > 0)
        lv_obj_scroll_to_y(ui.term_scroll, lv_obj_get_scroll_y(ui.term_scroll) + bottom, LV_ANIM_OFF);
    ui.term_scrolling = false;
    if(ui.term_open && ui.pending == NONE) send_request(TERM_OPEN, "term.open");
}

static void terminal_scrolled(lv_event_t *event)
{
    (void)event;
    if(!ui.term_scroll || ui.term_scrolling) return;
    ui.term_follow = false;
    lv_obj_add_flag(ui.term_cursor, LV_OBJ_FLAG_HIDDEN);
    lv_obj_remove_flag(ui.term_bottom, LV_OBJ_FLAG_HIDDEN);
}

static void terminal_reply(enum response kind, bool success, const char *body)
{
    if(kind == TERM_INPUT && ui.term_keyboard) {
        lv_obj_remove_state(ui.entry, LV_STATE_DISABLED);
        lv_obj_remove_state(ui.typing_keys, LV_STATE_DISABLED);
    }
    if(!success) {
        if(ui.term_open) puts("terminal_live=0");
        ui.term_open = false;
        ui.queued_key = NULL;
        ui.queued_submit = 0;
        lv_label_set_text(ui.term_output, "");
        lv_obj_add_flag(ui.term_cursor, LV_OBJ_FLAG_HIDDEN);
        lv_label_set_text(ui.status, body);
        return;
    }
    if(kind == TERM_OPEN) {
        ui.term_open = true;
        puts("terminal_live=1");
        lv_label_set_text(ui.status, "");
    } else if(kind == TERM_INPUT) {
        if(ui.term_utf8) puts("terminal_utf8_sent=1");
        lv_textarea_set_text(ui.entry, "");
        if(ui.term_enter) terminal_key("Enter");
    } else if(kind == TERM_KEY) {
        printf("terminal_key_sent=%s\n", ui.sent_key);
    }
    if(kind == TERM_OPEN || kind == TERM_POLL) {
        if(*body == '\n' && ui.term_follow) {
            char *end;
            long cursor = strtol(body + 1, &end, 10);
            if(*end != '\n') return;
            lv_label_set_text(ui.term_output, end + 1);
            ui.term_scrolling = true;
            lv_obj_update_layout(ui.term_scroll);
            if(cursor >= 0 && cursor <= 16000) {
                lv_point_t point;
                lv_label_get_letter_pos(ui.term_output, (uint32_t)cursor, &point);
                lv_obj_set_pos(ui.term_cursor, 10 + point.x, 6 + point.y);
                lv_obj_remove_flag(ui.term_cursor, LV_OBJ_FLAG_HIDDEN);
            } else {
                lv_obj_add_flag(ui.term_cursor, LV_OBJ_FLAG_HIDDEN);
            }
            int bottom = lv_obj_get_scroll_bottom(ui.term_scroll);
            if(bottom > 0)
                lv_obj_scroll_to_y(ui.term_scroll, lv_obj_get_scroll_y(ui.term_scroll) + bottom, LV_ANIM_OFF);
            ui.term_scrolling = false;
        }
    } else {
        ui.term_last_poll = lv_tick_get() - 350;
    }
}

static void terminal_poll(lv_timer_t *timer)
{
    (void)timer;
    if(!ui.term_open || ui.pending != NONE) return;
    if(ui.queued_submit) {
        bool enter = ui.queued_submit == 2;
        ui.queued_submit = 0;
        submit_terminal(enter);
    } else if(ui.queued_key) {
        const char *key = ui.queued_key;
        ui.queued_key = NULL;
        terminal_key(key);
    } else if(ui.term_follow && lv_tick_elaps(ui.term_last_poll) >= 350) {
        ui.term_last_poll = lv_tick_get();
        send_request(TERM_POLL, "term.poll");
    }
}

static void connect_terminal(lv_event_t *event)
{
    (void)event;
    ui.term_follow = true;
    lv_obj_add_flag(ui.term_bottom, LV_OBJ_FLAG_HIDDEN);
    if(send_request(TERM_OPEN, "term.open"))
        ui.term_last_poll = lv_tick_get();
}

static void terminal_button(lv_event_t *event)
{
    terminal_key(lv_event_get_user_data(event));
}

static void submit_terminal(bool enter)
{
    const char *text = ui.term_keyboard ? lv_textarea_get_text(ui.entry) : "";
    if(!ui.term_open) return;
    if(ui.pending != NONE) {
        ui.queued_submit = enter ? 2 : 1;
        return;
    }
    if(ui.composition && *lv_textarea_get_text(ui.composition)) {
        lv_label_set_text(ui.status, tr("请先选择拼音候选词。", "Choose a Pinyin candidate first."));
        return;
    }
    if(!*text) {
        if(enter) terminal_key("Enter");
        return;
    }
    if(strpbrk(text, "\t\r\n")) return;
    char request[1040];
    int len = snprintf(request, sizeof(request), "term.input\t%s", text);
    if(len > 0 && len < (int)sizeof(request) && send_request(TERM_INPUT, request)) {
        ui.term_enter = enter;
        ui.term_utf8 = false;
        for(const unsigned char *p = (const unsigned char *)text; *p; ++p)
            ui.term_utf8 |= *p >= 128;
        lv_obj_add_state(ui.entry, LV_STATE_DISABLED);
        lv_obj_add_state(ui.typing_keys, LV_STATE_DISABLED);
    }
}

static void terminal_submit(lv_event_t *event)
{
    submit_terminal(lv_event_get_user_data(event) != NULL);
}

static void show_candidates(const char *body)
{
    bool fresh = ui.composition && strcmp(lv_textarea_get_text(ui.composition), ui.lookup) == 0;
    for(unsigned i = 0; i < 6; ++i) {
        lv_obj_t *item = ui.candidates[i];
        if(!fresh || !*body) {
            lv_obj_add_flag(item, LV_OBJ_FLAG_HIDDEN);
            continue;
        }
        const char *end = strchr(body, '\n');
        size_t length = end ? (size_t)(end - body) : strlen(body);
        lv_label_set_text_fmt(lv_obj_get_child(item, 0), "%.*s", (int)length, body);
        lv_obj_remove_flag(item, LV_OBJ_FLAG_HIDDEN);
        body += length + (end != NULL);
    }
    lv_label_set_text(ui.status, fresh && !lv_obj_has_flag(ui.candidates[0], LV_OBJ_FLAG_HIDDEN)
                      ? "" : tr("输入完整拼音后选择候选词。", "Enter Pinyin and choose a candidate."));
}

static void lookup_pinyin(lv_timer_t *timer)
{
    (void)timer;
    if(!ui.composition || ui.pending != NONE) return;
    const char *code = lv_textarea_get_text(ui.composition);
    if(strcmp(code, ui.lookup) == 0) return;
    snprintf(ui.lookup, sizeof(ui.lookup), "%s", code);
    show_candidates("");
    if(!*code) return;
    char request[48];
    snprintf(request, sizeof(request), "text.lookup\t%s", code);
    send_request(PINYIN_CANDIDATES, request);
}

static void choose_pinyin(lv_event_t *event)
{
    if(ui.pending != NONE || strcmp(lv_textarea_get_text(ui.composition), ui.lookup) != 0) return;
    lv_obj_t *item = lv_event_get_target(event);
    lv_textarea_add_text(ui.entry, lv_label_get_text(lv_obj_get_child(item, 0)));
    lv_textarea_set_text(ui.composition, "");
    ui.lookup[0] = 0;
    show_candidates("");
}

static int term_y(int y)
{
    return y + (ui.portrait ? 680 : 0);
}

static void toggle_pinyin(lv_event_t *event)
{
    if(event && ui.pending != NONE && ui.pending != TERM_POLL) return;
    bool terminal = ui.term_scroll != NULL;
    if(ui.composition) {
        lv_keyboard_set_textarea(ui.typing_keys, ui.entry);
        lv_obj_delete(ui.composition);
        ui.composition = NULL;
        for(unsigned i = 0; i < 6; ++i) lv_obj_delete(ui.candidates[i]);
        lv_obj_set_y(ui.typing_keys, terminal ? term_y(560) : 155);
        lv_obj_set_height(ui.typing_keys, terminal ? 420 : 720);
        lv_obj_set_y(ui.ime_switch, terminal ? term_y(445) : 884);
        if(terminal) lv_obj_set_width(ui.entry, sx(2090));
        lv_label_set_text(lv_obj_get_child(ui.ime_switch, 0), tr("中文拼音", "Pinyin"));
        lv_label_set_text(ui.status, "");
    } else {
        ui.lookup[0] = 0;
        ui.composition = terminal ? entry(1240, term_y(445), 850, 24, "nihao") : entry(460, 132, 2240, 24, "nihao");
        lv_textarea_set_accepted_chars(ui.composition, "abcdefghijklmnopqrstuvwxyz");
        lv_obj_set_y(ui.ime_switch, terminal ? term_y(445) : 132);
        if(terminal) lv_obj_set_width(ui.entry, sx(1200));
        lv_label_set_text(lv_obj_get_child(ui.ime_switch, 0), "ABC");
        lv_obj_set_y(ui.typing_keys, terminal ? term_y(668) : 370);
        lv_obj_set_height(ui.typing_keys, terminal ? 312 : 610);
        lv_keyboard_set_mode(ui.typing_keys, LV_KEYBOARD_MODE_TEXT_LOWER);
        lv_keyboard_set_textarea(ui.typing_keys, ui.composition);
        for(unsigned i = 0; i < 6; ++i) {
            ui.candidates[i] = button(ui.body, "", (int)i * 450, terminal ? term_y(561) : 249, 430, choose_pinyin, NULL);
            if(terminal) lv_obj_set_height(ui.candidates[i], 102);
        }
        show_candidates("");
    }
}

static void toggle_terminal_keyboard(lv_event_t *event)
{
    if(event && ui.pending != NONE && ui.pending != TERM_POLL) return;
    if(ui.term_keyboard) {
        if(*lv_textarea_get_text(ui.entry) || (ui.composition && *lv_textarea_get_text(ui.composition))) {
            lv_label_set_text(ui.status, tr("请先发送或清空输入。", "Send or clear the input first."));
            return;
        }
        if(ui.composition) {
            if(ui.pending != NONE) return;
            toggle_pinyin(NULL);
        }
        lv_obj_delete(ui.typing_keys);
        lv_obj_delete(ui.entry);
        ui.entry = NULL;
        if(ui.chinese) lv_obj_delete(ui.ime_switch);
        lv_obj_add_flag(ui.term_send_button, LV_OBJ_FLAG_HIDDEN);
        lv_obj_set_height(ui.term_scroll, ui.body_height - (ui.portrait ? 278 : 145));
        lv_label_set_text(lv_obj_get_child(ui.term_keyboard_button, 0), tr("键盘", "Keyboard"));
    } else {
        ui.term_scrolling = true;
        lv_obj_set_height(ui.term_scroll, ui.portrait ? 850 : 310);
        lv_obj_update_layout(ui.term_scroll);
        int bottom = lv_obj_get_scroll_bottom(ui.term_scroll);
        if(bottom > 0) lv_obj_scroll_to_y(ui.term_scroll, lv_obj_get_scroll_y(ui.term_scroll) + bottom, LV_ANIM_OFF);
        ui.term_scrolling = false;
        ui.entry = entry(0, term_y(445), 2090, 256, tr("输入命令或文字", "Type a command or text"));
        ui.typing_keys = keyboard(ui.entry, term_y(560));
        lv_obj_set_height(ui.typing_keys, 420);
        lv_obj_add_event_cb(ui.typing_keys, terminal_submit, LV_EVENT_READY, NULL);
        if(ui.chinese)
            ui.ime_switch = button(ui.body, tr("中文拼音", "Pinyin"), 2120, term_y(445), 580, toggle_pinyin, NULL);
        lv_obj_remove_flag(ui.term_send_button, LV_OBJ_FLAG_HIDDEN);
        lv_label_set_text(lv_obj_get_child(ui.term_keyboard_button, 0), tr("收起", "Hide"));
    }
    ui.term_keyboard = !ui.term_keyboard;
}

static void show_terminal(void)
{
    if(!ui.term_font && access("/usr/share/fonts/droid/DroidSansMono.ttf", R_OK) == 0) {
        ui.term_font = lv_freetype_font_create("/usr/share/fonts/droid/DroidSansMono.ttf",
                                              LV_FREETYPE_FONT_RENDER_MODE_BITMAP, 40,
                                              LV_FREETYPE_FONT_STYLE_NORMAL);
        if(ui.term_font) ui.term_font->fallback = lv_obj_get_style_text_font(ui.status, 0);
    }
    const char *labels[] = {tr("键盘", "Keys"), "Tab", "Esc", LV_SYMBOL_LEFT, LV_SYMBOL_UP,
                           LV_SYMBOL_DOWN, LV_SYMBOL_RIGHT, "Ctrl+C", tr("回车", "Enter"),
                           tr("发送", "Send"), tr("到底部", "Bottom"), tr("接入", "Connect")};
    const char *keys[] = {"Tab", "Escape", "Left", "Up", "Down", "Right", "C-c"};
    const int landscape_widths[] = {315, 160, 160, 150, 150, 150, 150, 230, 220, 250, 290, 310};
    int x = 0;
    for(unsigned i = 0; i < 12; ++i) {
        int width = ui.portrait ? 430 : landscape_widths[i];
        int y = ui.portrait && i >= 6 ? 125 : 0;
        if(ui.portrait && i == 6) x = 0;
        lv_event_cb_t callback = i == 0 ? toggle_terminal_keyboard : i < 8 ? terminal_button :
                                 i < 10 ? terminal_submit : i == 10 ? terminal_follow : connect_terminal;
        void *arg = i > 0 && i < 8 ? (void *)keys[i - 1] : i == 8 ? (void *)1 : NULL;
        lv_obj_t *key = button(ui.body, labels[i], x, y, width, callback, arg);
        if(i >= 3 && i <= 6) lv_obj_set_style_text_font(lv_obj_get_child(key, 0), &lv_font_montserrat_48, 0);
        if(i == 0) ui.term_keyboard_button = key;
        if(i == 9) {
            ui.term_send_button = key;
            lv_obj_add_flag(key, LV_OBJ_FLAG_HIDDEN);
        }
        if(i == 10) ui.term_bottom = key;
        x += width + 15;
    }
    ui.term_scroll = lv_obj_create(ui.body);
    int toolbar = ui.portrait ? 260 : 127;
    lv_obj_set_pos(ui.term_scroll, 0, toolbar);
    lv_obj_set_size(ui.term_scroll, sx(2700), ui.body_height - toolbar - 18);
    lv_obj_set_scroll_dir(ui.term_scroll, LV_DIR_ALL);
    lv_obj_add_event_cb(ui.term_scroll, terminal_scrolled, LV_EVENT_SCROLL_BEGIN, NULL);
    ui.term_output = label(ui.term_scroll, "", 10, 6);
    if(ui.term_font) lv_obj_set_style_text_font(ui.term_output, ui.term_font, 0);
    ui.term_cursor = lv_obj_create(ui.term_scroll);
    lv_obj_remove_flag(ui.term_cursor, LV_OBJ_FLAG_CLICKABLE | LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_set_size(ui.term_cursor, 5, 37);
    lv_obj_set_style_border_width(ui.term_cursor, 0, 0);
    lv_obj_set_style_radius(ui.term_cursor, 0, 0);
    lv_obj_set_style_bg_color(ui.term_cursor, lv_color_hex(0x6fd0be), 0);
    lv_obj_add_flag(ui.term_cursor, LV_OBJ_FLAG_HIDDEN);
    connect_terminal(NULL);
}

static void show_unlock(void)
{
    label(ui.body, tr("输入 6 位面板 PIN", "Enter the six-digit panel PIN"), 0, 3);
    ui.entry = entry(0, 80, 2050, 6, tr("6 位数字", "Six digits"));
    lv_textarea_set_accepted_chars(ui.entry, "0123456789");
    lv_textarea_set_password_mode(ui.entry, true);
    lv_textarea_set_password_show_time(ui.entry, 0);
    button(ui.body, tr("打开面板", "Unlock"), 2100, 80, 600, unlock_panel, NULL);
    lv_obj_t *keys = keyboard(ui.entry, 242);
    static const char *const digits[] = {
        "1", "2", "3", "4", "5", "6", "\n", "7", "8", "9", "0", LV_SYMBOL_BACKSPACE, "",
    };
    static lv_buttonmatrix_ctrl_t flags[11];
    for(unsigned i = 0; i < sizeof(flags) / sizeof(flags[0]); i++)
        flags[i] = LV_KEYBOARD_CTRL_BUTTON_FLAGS | 1;
    flags[10] = LV_KEYBOARD_CTRL_BUTTON_FLAGS | 2;
    lv_keyboard_set_map(keys, LV_KEYBOARD_MODE_USER_2, digits, flags);
    lv_keyboard_set_mode(keys, LV_KEYBOARD_MODE_USER_2);
}

static void dropdown(int width)
{
    ui.list = lv_dropdown_create(ui.body);
    lv_obj_set_pos(ui.list, 0, 0);
    lv_obj_set_size(ui.list, sx(width), 110);
    lv_dropdown_set_options(ui.list, tr("暂无条目", "No entries"));
    lv_obj_set_style_max_height(lv_dropdown_get_list(ui.list), 780, 0);
}

static void reading_area(int y)
{
    lv_obj_t *scroll = lv_obj_create(ui.body);
    lv_obj_set_pos(scroll, 0, y);
    lv_obj_set_size(scroll, sx(2700), ui.body_height - 10 - y);
    lv_obj_set_scroll_dir(scroll, LV_DIR_VER);
    ui.detail = label(scroll, "", 22, 18);
    lv_obj_set_width(ui.detail, sx(2570));
    lv_label_set_long_mode(ui.detail, LV_LABEL_LONG_WRAP);
}

static void show_records(const char *body, bool missed)
{
    lv_obj_clean(ui.detail);
    lv_obj_scroll_to_y(ui.detail, 0, LV_ANIM_OFF);
    lv_label_set_text(ui.status, *body
                      ? (missed ? tr("点一条记录回拨", "Tap a call to call back") : "")
                      : tr("暂无记录", "No records"));
    for(unsigned i = 0; *body; ++i) {
        const char *end = strchr(body, '\n');
        size_t length = end ? (size_t)(end - body) : strlen(body);
        char line[512];
        if(length >= sizeof(line)) length = sizeof(line) - 1;
        while(((unsigned char)body[length] & 0xc0) == 0x80) --length;
        snprintf(line, sizeof(line), "%.*s", (int)length, body);
        lv_obj_t *row = button(ui.detail, line, 0, (int)i * 132, 2600,
                              missed ? select_missed : read_message, (void *)(uintptr_t)i);
        lv_obj_t *caption = lv_obj_get_child(row, 0);
        lv_obj_set_width(caption, sx(2500));
        lv_label_set_long_mode(caption, LV_LABEL_LONG_DOT);
        lv_obj_align(caption, LV_ALIGN_LEFT_MID, 32, 0);
        if(!end) break;
        body = end + 1;
    }
}

static void show_message(const char *body)
{
    ui.sms_body = true;
    ui.entry = NULL;
    ui.list = NULL;
    set_shade(0);
    ui.page = SMS;
    select_tab(2);
    memset(ui.overview_notice, 0, sizeof(ui.overview_notice));
    ui.hero_clock = ui.hero_date = ui.home_wifi = ui.notice_hint = ui.media_clock = NULL;
    lv_obj_clean(ui.body);
    lv_label_set_text(ui.status, "");
    button(ui.body, tr("返回列表", "Back to list"), 0, 0, 550, sms_back, NULL);
    reading_area(140);
    lv_label_set_text(ui.detail, body);
}

static void home_refresh(lv_event_t *event)
{
    (void)event;
    send_request(OVERVIEW, "overview.status");
}

static void home_toggle(lv_event_t *event)
{
    if(!ui.shade_level) return;
    unsigned i = (unsigned)(uintptr_t)lv_event_get_user_data(event);
    const char *actions[] = {"wifi.power", "bt.power", "mobile.data"};
    char request[48];
    snprintf(request, sizeof(request), "overview.set\t%s\t%s", actions[i], ui.home_network[i] ? "off" : "on");
    send_request(OVERVIEW, request);
}

static void latest_notice(lv_event_t *event)
{
    if(lv_event_get_user_data(event))
        send_request(SMS_BODY, "sms.latest");
    else
        send_request(CALLBACK_NUMBER, "phone.latest");
}

static void overview_reply(const char *body)
{
    int wifi, bt, mobile, missed, sms, battery, charging, signal, brightness, connected, torch, length = 0;
    if(sscanf(body, "%d %d %d %d %d %d %d %d %d %d %d%n", &wifi, &bt, &mobile, &missed, &sms,
              &battery, &charging, &signal, &brightness, &connected, &torch, &length) != 11 ||
       body[length] != '\n' || wifi < 0 || wifi > 1 || bt < 0 || bt > 1 || mobile < 0 || mobile > 2) {
        lv_label_set_text(ui.status, tr("无法读取系统状态", "System status unavailable"));
        return;
    }
    const char *technology = body + length + 1;
    if(strcmp(technology, "2G") && strcmp(technology, "3G") && strcmp(technology, "4G") &&
       strcmp(technology, "5G")) technology = "";
    const char *bars[] = {"–", "▂", "▂▄", "▂▄▆", "▂▄▆█"};
    lv_label_set_text_fmt(ui.signals, "%s %s", technology,
                          bars[signal <= 0 ? 0 : LV_MIN(4, 1 + signal / 25)]);
    const char *battery_icons[] = {LV_SYMBOL_BATTERY_EMPTY, LV_SYMBOL_BATTERY_1,
        LV_SYMBOL_BATTERY_2, LV_SYMBOL_BATTERY_3, LV_SYMBOL_BATTERY_FULL};
    char capacity[12] = "";
    if(battery >= 0 && battery <= 100) snprintf(capacity, sizeof(capacity), "%d%%", battery);
    lv_label_set_text_fmt(ui.system_icons, "%s%s%s%s%s %s",
                         bt ? LV_SYMBOL_BLUETOOTH "  " : "",
                         connected ? LV_SYMBOL_WIFI "  " : "",
                         charging ? LV_SYMBOL_CHARGE " " : "",
                         *capacity ? battery_icons[LV_MIN(4, battery / 25)] : "",
                         *capacity ? " " : "", capacity);
    lv_label_set_text_fmt(ui.notice_icons, "%s%s", missed > 0 ? LV_SYMBOL_CALL "  " : "",
                         sms > 0 ? LV_SYMBOL_ENVELOPE : "");
    const int states[] = {wifi, bt, mobile};
    for(unsigned i = 0; i < 3; ++i) {
        ui.home_network[i] = states[i];
        lv_obj_set_style_bg_color(ui.home_switch[i], lv_color_hex(states[i] ? 0x254942 : 0x212d35), 0);
        lv_label_set_text(ui.tile_state[i], states[i] == 2 ? tr("等待连接", "Waiting")
            : states[i] ? tr("开启", "On") : tr("关闭", "Off"));
        lv_obj_remove_state(ui.home_switch[i], LV_STATE_DISABLED);
    }
    lv_obj_t *slider = ui.brightness;
    if(ui.home_wifi) lv_label_set_text(ui.home_wifi, connected ? tr("已连接", "Connected")
        : wifi ? tr("已开启", "On") : tr("已关闭", "Off"));
    if(!lv_obj_has_state(slider, LV_STATE_PRESSED)) {
        if(brightness < 0 || brightness > 100) {
            lv_obj_add_state(slider, LV_STATE_DISABLED);
            lv_label_set_text(ui.brightness_value, "—");
        }
        else {
            lv_obj_remove_state(slider, LV_STATE_DISABLED);
            lv_slider_set_value(slider, brightness, LV_ANIM_OFF);
            lv_label_set_text_fmt(ui.brightness_value, "%d%%", brightness);
        }
    }
    if(torch == 0 || torch == 1) {
        lv_obj_remove_flag(ui.torch, LV_OBJ_FLAG_HIDDEN);
        lv_obj_set_style_bg_color(ui.torch, lv_color_hex(torch ? 0x254942 : 0x212d35), 0);
    } else lv_obj_add_flag(ui.torch, LV_OBJ_FLAG_HIDDEN);
    const int counts[] = {missed, sms};
    const char *notice[] = {tr("未接来电  ·  %d", "Missed calls  ·  %d"),
                            tr("未读短信  ·  %d", "Unread messages  ·  %d")};
    for(unsigned i = 0; i < 2; ++i) {
        lv_obj_t *items[] = {ui.home_notice[i], ui.overview_notice[i]};
        for(unsigned n = 0; n < 2; ++n) {
            if(!items[n]) continue;
            if(counts[i] > 0) {
                lv_label_set_text_fmt(lv_obj_get_child(items[n], 0), notice[i], counts[i]);
                lv_obj_remove_flag(items[n], LV_OBJ_FLAG_HIDDEN);
            } else {
                lv_obj_add_flag(items[n], LV_OBJ_FLAG_HIDDEN);
            }
        }
    }
    const char *empty = missed < 0 || sms < 0 ? tr("通知暂不可用", "Notifications unavailable")
                                              : tr("暂无新通知", "No new notifications");
    lv_label_set_text(ui.shade_hint, missed > 0 || sms > 0 ? "" : empty);
    if(ui.notice_hint) lv_label_set_text(ui.notice_hint, missed > 0 || sms > 0 ? "" : empty);
    lv_label_set_text(ui.status, "");
}

static void set_shade(int level)
{
    ui.shade_level = level;
    if(!ui.shade) return;
    if(level) {
        lv_obj_remove_flag(ui.shade_backdrop, LV_OBJ_FLAG_HIDDEN);
        lv_obj_remove_flag(ui.shade, LV_OBJ_FLAG_HIDDEN);
    } else {
        lv_obj_add_flag(ui.shade_backdrop, LV_OBJ_FLAG_HIDDEN);
        lv_obj_add_flag(ui.shade, LV_OBJ_FLAG_HIDDEN);
    }
    lv_obj_set_height(ui.shade, ui.shade_compact_height + (level == 2 ? 300 : 0));
    lv_label_set_text(ui.shade_handle_label, level == 2 ? tr("收起", "Close") : tr("展开", "Expand"));
    if(level == 2) lv_obj_remove_flag(ui.shade_content, LV_OBJ_FLAG_HIDDEN);
    else lv_obj_add_flag(ui.shade_content, LV_OBJ_FLAG_HIDDEN);
}

static void shade_handle(lv_event_t *event)
{
    if(!ui.panel_unlocked || ui.rotating) return;
    if(lv_event_get_code(event) == LV_EVENT_GESTURE) {
        lv_indev_t *pointer = lv_indev_active();
        lv_dir_t direction = lv_indev_get_gesture_dir(pointer);
        if(direction == LV_DIR_BOTTOM) set_shade(LV_MIN(2, ui.shade_level + 1));
        else if(direction == LV_DIR_TOP) set_shade(0);
        else return;
        lv_indev_wait_release(pointer);
    } else {
        set_shade((ui.shade_level + 1) % 3);
    }
    if(ui.shade_level == 1 && ui.pending == NONE) home_refresh(NULL);
}

static void system_refresh(lv_timer_t *timer)
{
    (void)timer;
    time_t now = time(NULL);
    struct tm local;
    char clock[12];
    if(!localtime_r(&now, &local) || !strftime(clock, sizeof(clock), "%H:%M", &local)) return;
    if(strcmp(clock, lv_label_get_text(ui.clock))) lv_label_set_text(ui.clock, clock);
    if(ui.hero_clock && strcmp(clock, lv_label_get_text(ui.hero_clock))) {
        static const char *days[] = {"周日", "周一", "周二", "周三", "周四", "周五", "周六"};
        lv_label_set_text(ui.hero_clock, clock);
        if(ui.chinese) lv_label_set_text_fmt(ui.hero_date, "%d月%d日  ·  %s", local.tm_mon + 1,
                                             local.tm_mday, days[local.tm_wday]);
        else {
            char date[36];
            if(strftime(date, sizeof(date), "%a, %b %d", &local)) lv_label_set_text(ui.hero_date, date);
        }
    }
    if(ui.media_clock && ui.recording) {
        unsigned seconds = LV_MIN(60, lv_tick_elaps(ui.media_start) / 1000);
        char elapsed[12];
        snprintf(elapsed, sizeof(elapsed), "%02u:%02u", seconds / 60, seconds % 60);
        if(strcmp(elapsed, lv_label_get_text(ui.media_clock))) lv_label_set_text(ui.media_clock, elapsed);
    }
}

static void refresh_status(lv_timer_t *timer)
{
    (void)timer;
    if(ui.panel_unlocked && (ui.page == NETWORK || ui.shade_level) && !ui.recording && !ui.playing && ui.pending == NONE && !lv_obj_has_state(ui.brightness, LV_STATE_PRESSED)) {
        ui.status_refresh = true;
        if(!send_request(OVERVIEW, "overview.status")) ui.status_refresh = false;
    }
}

static void brightness_preview(lv_event_t *event)
{
    lv_label_set_text_fmt(ui.brightness_value, "%d%%", (int)lv_slider_get_value(lv_event_get_target(event)));
}

static void brightness_set(lv_event_t *event)
{
    char request[32];
    snprintf(request, sizeof(request), "brightness.set\t%d", (int)lv_slider_get_value(lv_event_get_target(event)));
    send_request(OVERVIEW, request);
}

bool panel_ui_rotate(lv_display_rotation_t rotation, lv_indev_t *touch)
{
    if(rotation == lv_display_get_rotation(ui.display)) return true;
    if(ui.pending != NONE || ui.rotating || ui.queued_key || ui.queued_submit) return false;
    if(touch) lv_indev_reset(touch, NULL);
    lv_display_set_rotation(ui.display, rotation);
    ui.rotation_flip_pending = true;
    lv_obj_invalidate(ui.screen);
    if(ui.portrait == is_portrait(rotation)) return true;

    const bool locked = ui.hardware_key && !ui.panel_unlocked;
    const bool terminal_keyboard = ui.term_keyboard;
    const bool pinyin = ui.composition != NULL;
    const int shade = ui.shade_level;
    const enum page page = ui.page;
    const bool wifi_ready = page == WIFI && ui.list_ready;
    const uint32_t wifi_selected = wifi_ready ? lv_dropdown_get_selected(ui.list) : 0;
    char *wifi_options = wifi_ready ? strdup(lv_dropdown_get_options(ui.list)) : NULL;
    char *message = page == SMS && ui.sms_body ? strdup(lv_label_get_text(ui.detail)) : NULL;
    const int32_t message_scroll = message ? lv_obj_get_scroll_y(lv_obj_get_parent(ui.detail)) : 0;
    const uint32_t cursor = ui.entry ? lv_textarea_get_cursor_pos(ui.entry) : 0;
    char draft[1025], composition[25];
    snprintf(draft, sizeof(draft), "%s", ui.entry ? lv_textarea_get_text(ui.entry) : "");
    snprintf(composition, sizeof(composition), "%s", pinyin ? lv_textarea_get_text(ui.composition) : "");

    ui.portrait = is_portrait(rotation);
    build_screen();
    if(locked) {
        show_unlock();
    } else {
        if(!ui.input_only) add_tabs();
        if(message) {
            show_message(message);
            lv_obj_update_layout(ui.detail);
            lv_obj_scroll_to_y(lv_obj_get_parent(ui.detail), message_scroll, LV_ANIM_OFF);
        } else {
            show_page(page);
            if(terminal_keyboard) toggle_terminal_keyboard(NULL);
            if(pinyin) toggle_pinyin(NULL);
            if(wifi_options) {
                lv_dropdown_set_options(ui.list, wifi_options);
                lv_dropdown_set_selected(ui.list, wifi_selected);
                ui.list_ready = true;
            }
        }
    }
    if(ui.entry) {
        lv_textarea_set_text(ui.entry, draft);
        lv_textarea_set_cursor_pos(ui.entry, (int32_t)cursor);
    }
    if(ui.composition) lv_textarea_set_text(ui.composition, composition);
    explicit_bzero(draft, sizeof(draft));
    free(wifi_options);
    free(message);
    set_shade(shade);
    return true;
}

static void rotate_now(lv_timer_t *timer)
{
    (void)timer;
    ui.rotating = false;
    panel_ui_rotate(ui.portrait ? LV_DISPLAY_ROTATION_270 : LV_DISPLAY_ROTATION_0, NULL);
}

static void rotate(lv_event_t *event)
{
    (void)event;
    if(ui.pending != NONE || ui.rotating) return;
    if(ui.page != NETWORK) {
        lv_label_set_text(ui.status, tr("请在总览切换方向", "Rotate from Overview"));
        return;
    }
    ui.rotating = true;
    lv_timer_t *timer = lv_timer_create(rotate_now, 20, NULL);
    lv_timer_set_repeat_count(timer, 1);
}

static void open_shade(lv_event_t *event)
{
    (void)event;
    set_shade(1);
    if(ui.pending == NONE) home_refresh(NULL);
}

static void torch_toggle(lv_event_t *event)
{
    (void)event;
    send_request(OVERVIEW, "torch.toggle");
}

static void close_shade(lv_event_t *event)
{
    (void)event;
    set_shade(0);
}

static void build_shade(void)
{
    ui.shade_backdrop = lv_obj_create(ui.screen);
    lv_obj_set_pos(ui.shade_backdrop, 0, 368);
    lv_obj_set_size(ui.shade_backdrop, lv_pct(100), ui.body_height + 55);
    lv_obj_remove_flag(ui.shade_backdrop, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_set_style_radius(ui.shade_backdrop, 0, 0);
    lv_obj_set_style_border_width(ui.shade_backdrop, 0, 0);
    lv_obj_set_style_bg_color(ui.shade_backdrop, lv_color_black(), 0);
    lv_obj_set_style_bg_opa(ui.shade_backdrop, LV_OPA_80, 0);
    lv_obj_add_event_cb(ui.shade_backdrop, close_shade, LV_EVENT_CLICKED, NULL);
    ui.shade = lv_obj_create(ui.screen);
    lv_obj_set_pos(ui.shade, sx(90), 368);
    lv_obj_set_size(ui.shade, sx(2700), ui.body_height + 35);
    lv_obj_remove_flag(ui.shade, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_remove_flag(ui.shade, LV_OBJ_FLAG_GESTURE_BUBBLE);
    lv_obj_add_event_cb(ui.shade, shade_handle, LV_EVENT_GESTURE, NULL);
    lv_obj_set_style_bg_color(ui.shade, lv_color_hex(0x111c24), 0);
    lv_obj_set_style_radius(ui.shade, 52, 0);
    lv_obj_set_style_pad_all(ui.shade, 0, 0);
    lv_obj_set_style_border_width(ui.shade, 0, 0);
    lv_obj_t *title = label(ui.shade, tr("快捷设置", "Quick settings"), 36, 28);
    lv_obj_set_style_text_color(title, lv_color_hex(0xd4eee5), 0);
    lv_obj_t *handle = button(ui.shade, tr("展开", "Expand"), 1880, 0, 820, shade_handle, NULL);
    ui.shade_handle_label = lv_obj_get_child(handle, 0);
    label(ui.shade, tr("亮度", "Brightness"), 36, 150);
    ui.brightness = lv_slider_create(ui.shade);
    lv_obj_set_pos(ui.brightness, sx(520), 151);
    lv_obj_set_size(ui.brightness, sx(1730), 52);
    ui.brightness_value = label(ui.shade, "—", 2365, 138);
    lv_obj_set_style_text_color(ui.brightness_value, lv_color_hex(0x98cdbc), 0);
    lv_obj_add_event_cb(ui.brightness, brightness_preview, LV_EVENT_VALUE_CHANGED, NULL);
    lv_slider_set_range(ui.brightness, 2, 100);
    lv_obj_add_state(ui.brightness, LV_STATE_DISABLED);
    lv_obj_add_event_cb(ui.brightness, brightness_set, LV_EVENT_RELEASED, NULL);
    const char *tiles[] = {"Wi-Fi", tr("蓝牙", "Bluetooth"), tr("蜂窝数据", "Data"), tr("声音", "Sound")};
    const char *icons[] = {LV_SYMBOL_WIFI, LV_SYMBOL_BLUETOOTH, LV_SYMBOL_UPLOAD, LV_SYMBOL_VOLUME_MID};
    const enum page pages[] = {WIFI, BLUETOOTH, MOBILE, AUDIO};
    for(unsigned i = 0; i < 4; ++i) {
        int x = ui.portrait ? (int)(i % 2) * 1350 : (int)i * 675;
        int y = 250 + (ui.portrait ? (int)(i / 2) * 158 : 0);
        lv_obj_t *tile = button(ui.shade, tiles[i], x + 12, y, ui.portrait ? 1300 : 632,
                                i < 3 ? home_toggle : tab, (void *)(uintptr_t)(i < 3 ? i : (unsigned)pages[i]));
        lv_obj_set_height(tile, 138);
        lv_obj_set_style_radius(tile, 38, 0);
        lv_obj_t *icon = label(tile, icons[i], 0, 0);
        lv_obj_set_style_text_font(icon, &lv_font_montserrat_48, 0);
        lv_obj_align(icon, LV_ALIGN_LEFT_MID, 25, 0);
        lv_obj_align(lv_obj_get_child(tile, 0), LV_ALIGN_LEFT_MID, 100, i < 3 ? -24 : 0);
        if(i < 3) {
            ui.home_switch[i] = tile;
            ui.tile_state[i] = label(tile, "", 0, 0);
            lv_obj_align(ui.tile_state[i], LV_ALIGN_LEFT_MID, 100, 28);
            lv_obj_set_style_text_color(ui.tile_state[i], lv_color_hex(0xb0c7c3), 0);
            lv_obj_add_state(tile, LV_STATE_DISABLED);
            lv_obj_add_event_cb(tile, tab, LV_EVENT_LONG_PRESSED, (void *)(uintptr_t)pages[i]);
        }
    }
    int notices_y = ui.portrait ? 576 : 418;
    ui.shade_compact_height = notices_y + 145;
    for(unsigned i = 0; i < 2; ++i) {
        ui.home_notice[i] = button(ui.shade, "", 12 + i * 1350, notices_y, 1300, latest_notice,
                                   (void *)(uintptr_t)i);
        lv_obj_add_flag(ui.home_notice[i], LV_OBJ_FLAG_HIDDEN);
    }
    ui.shade_hint = label(ui.shade, "", 40, notices_y + 27);
    lv_obj_set_style_text_color(ui.shade_hint, lv_color_hex(0x98aeba), 0);
    ui.shade_content = lv_obj_create(ui.shade);
    lv_obj_set_pos(ui.shade_content, 0, notices_y + 150);
    lv_obj_set_size(ui.shade_content, sx(2700), 320);
    lv_obj_remove_flag(ui.shade_content, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_set_style_bg_opa(ui.shade_content, LV_OPA_TRANSP, 0);
    lv_obj_set_style_border_width(ui.shade_content, 0, 0);
    lv_obj_set_style_pad_all(ui.shade_content, 0, 0);
    button(ui.shade_content, ui.portrait ? tr("切换横屏", "Landscape") : tr("切换竖屏", "Portrait"),
           12, 0, 1300, rotate, NULL);
    button(ui.shade_content, tr("打字", "Text"), 1362, 0, 1300, tab, (void *)(uintptr_t)TEXT);
    ui.torch = button(ui.shade_content, tr("手电筒", "Torch"), 12, 132, 1300, torch_toggle, NULL);
    lv_obj_add_flag(ui.torch, LV_OBJ_FLAG_HIDDEN);
    set_shade(0);
}

static void media_action(lv_event_t *event)
{
    const char *request = lv_event_get_user_data(event);
    if(ui.pending == MEDIA_STATE && strcmp(request, "media.stop") == 0)
        ui.media_stop_queued = true;
    else send_request(MEDIA_STATE, request);
}

static void poll_media(lv_timer_t *timer)
{
    (void)timer;
    if(ui.pending != NONE) return;
    if(ui.media_stop_queued) {
        ui.media_stop_queued = false;
        send_request(MEDIA_STATE, "media.stop");
    } else if((ui.recording || ui.playing) && lv_tick_elaps(ui.media_last_poll) >= 600) {
        ui.media_last_poll = lv_tick_get();
        ui.media_refresh = true;
        if(!send_request(MEDIA_STATE, "media.status")) ui.media_refresh = false;
    }
}

static void media_reply(const char *body)
{
    int recording, playing, ready, duration, result;
    if(sscanf(body, "%d %d %d %d %d", &recording, &playing, &ready, &duration, &result) != 5 ||
       duration < 0 || duration > 60000) return;
    if(!ui.recording && !ui.playing) ui.media_last_poll = lv_tick_get();
    if(recording && !ui.recording) ui.media_start = lv_tick_get();
    ui.recording = recording == 1;
    ui.playing = playing == 1;
    if(ui.recording) lv_obj_remove_flag(ui.mic, LV_OBJ_FLAG_HIDDEN);
    else lv_obj_add_flag(ui.mic, LV_OBJ_FLAG_HIDDEN);
    if(ui.page != MEDIA) return;
    bool busy = ui.recording || ui.playing;
    if(!ready) lv_label_set_text(ui.media_info, tr("当前系统未启用麦克风", "Microphone driver unavailable"));
    else if(result == 2) lv_label_set_text(ui.media_info, tr("未录到声音，未保存", "No audio captured"));
    else if(result == 3) lv_label_set_text(ui.media_info, tr("回听失败", "Playback failed"));
    else if(busy) lv_label_set_text(ui.media_info, ui.recording ? tr("录音中", "Recording") : tr("回听中", "Playing"));
    else if(duration) lv_label_set_text_fmt(ui.media_info,
        result == 1 ? tr("已保存  ·  %d.%d 秒", "Saved  ·  %d.%d s")
                    : tr("最近录音  ·  %d.%d 秒", "Last recording  ·  %d.%d s"), duration / 1000, (duration % 1000) / 100);
    else lv_label_set_text(ui.media_info, tr("暂无可回听录音", "No playable recordings"));
    if(ui.recording) lv_obj_remove_flag(ui.media_clock, LV_OBJ_FLAG_HIDDEN);
    else lv_obj_add_flag(ui.media_clock, LV_OBJ_FLAG_HIDDEN);
    system_refresh(NULL);
    if(busy || !ready) lv_obj_add_state(ui.media_record, LV_STATE_DISABLED);
    else lv_obj_remove_state(ui.media_record, LV_STATE_DISABLED);
    if(busy || !duration) lv_obj_add_state(ui.media_play, LV_STATE_DISABLED);
    else lv_obj_remove_state(ui.media_play, LV_STATE_DISABLED);
    if(busy) lv_obj_remove_state(ui.media_stop, LV_STATE_DISABLED);
    else lv_obj_add_state(ui.media_stop, LV_STATE_DISABLED);
    lv_label_set_text(ui.status, "");
}

static void show_media(void)
{
    lv_obj_t *card = lv_obj_create(ui.body);
    lv_obj_remove_flag(card, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_set_size(card, sx(2700), 208);
    lv_obj_set_style_radius(card, 48, 0);
    lv_obj_set_style_pad_all(card, 0, 0);
    lv_obj_set_style_border_width(card, 0, 0);
    lv_obj_set_style_bg_color(card, lv_color_hex(0x18262e), 0);
    lv_obj_t *icon = label(card, LV_SYMBOL_AUDIO, 65, 48);
    lv_obj_set_style_text_font(icon, &lv_font_montserrat_48, 0);
    lv_obj_set_style_text_color(icon, lv_color_hex(0xf3aa94), 0);
    label(card, tr("语音备忘", "Voice notes"), 220, 32);
    ui.media_info = label(card, "", 220, 114);
    lv_obj_set_style_text_color(ui.media_info, lv_color_hex(0xa8c0ca), 0);
    ui.media_clock = label(card, "00:00", 1920, 36);
    lv_obj_set_style_text_color(ui.media_clock, lv_color_hex(0xf3aa94), 0);
    lv_obj_add_flag(ui.media_clock, LV_OBJ_FLAG_HIDDEN);
    ui.media_record = button(ui.body, tr("录音", "Record"), 0, 255, 845, media_action, "media.record");
    ui.media_stop = button(ui.body, tr("停止", "Stop"), 920, 255, 845, media_action, "media.stop");
    ui.media_play = button(ui.body, tr("回听", "Play last"), 1840, 255, 845, media_action, "media.play");
    lv_obj_set_height(ui.media_record, 142);
    lv_obj_set_height(ui.media_stop, 142);
    lv_obj_set_height(ui.media_play, 142);
    lv_obj_set_style_bg_color(ui.media_record, lv_color_hex(0x5f3533), 0);
    lv_obj_set_style_bg_color(ui.media_stop, lv_color_hex(0x5f3533), 0);
    lv_obj_set_style_bg_color(ui.media_play, lv_color_hex(0x203e37), 0);
    lv_obj_add_state(ui.media_record, LV_STATE_DISABLED);
    lv_obj_add_state(ui.media_stop, LV_STATE_DISABLED);
    lv_obj_add_state(ui.media_play, LV_STATE_DISABLED);
    send_request(MEDIA_STATE, "media.status");
}

static void show_overview(void)
{
    if(!ui.hero_font) {
        if(ui.chinese)
            ui.hero_font = lv_freetype_font_create(V30_PANEL_FONT_PATH, LV_FREETYPE_FONT_RENDER_MODE_BITMAP,
                                                   132, LV_FREETYPE_FONT_STYLE_NORMAL);
        if(!ui.hero_font) ui.hero_font = &lv_font_montserrat_48;
    }
    ui.hero_clock = label(ui.body, "", 34, 16);
    lv_obj_set_style_text_font(ui.hero_clock, ui.hero_font, 0);
    lv_obj_set_style_text_color(ui.hero_clock, lv_color_hex(0xe5f2ed), 0);
    ui.hero_date = label(ui.body, "", 40, 176);
    lv_obj_set_style_text_color(ui.hero_date, lv_color_hex(0x9db5c1), 0);
    system_refresh(NULL);
    const char *titles[] = {tr("快捷设置", "Settings"), "Wi-Fi", tr("媒体", "Media")};
    const char *icons[] = {LV_SYMBOL_SETTINGS, LV_SYMBOL_WIFI, LV_SYMBOL_AUDIO};
    const enum page pages[] = {NETWORK, WIFI, MEDIA};
    for(unsigned i = 0; i < 3; ++i) {
        lv_obj_t *tile = button(ui.body, titles[i], i * 900, 285, 866,
                                i == 0 ? open_shade : tab, (void *)(uintptr_t)pages[i]);
        lv_obj_set_height(tile, 184);
        lv_obj_set_style_radius(tile, 46, 0);
        lv_obj_align(lv_obj_get_child(tile, 0), LV_ALIGN_LEFT_MID, 28, 35);
        lv_obj_t *icon = label(tile, icons[i], 0, 0);
        lv_obj_set_style_text_font(icon, &lv_font_montserrat_48, 0);
        lv_obj_set_style_text_color(icon, lv_color_hex(0x9be3cd), 0);
        lv_obj_align(icon, LV_ALIGN_LEFT_MID, 28, -36);
        if(i == 1) {
            ui.home_wifi = label(tile, "", 0, 0);
            lv_obj_set_style_text_color(ui.home_wifi, lv_color_hex(0x9db5c1), 0);
            lv_obj_align(ui.home_wifi, LV_ALIGN_RIGHT_MID, -24, -36);
        }
    }
    lv_obj_t *heading = label(ui.body, tr("通知", "Notifications"), 36, 539);
    lv_obj_set_style_text_color(heading, lv_color_hex(0xc4ddd4), 0);
    ui.notice_hint = label(ui.body, "", 36, 665);
    lv_obj_set_style_text_color(ui.notice_hint, lv_color_hex(0x98aeba), 0);
    for(unsigned i = 0; i < 2; ++i) {
        ui.overview_notice[i] = button(ui.body, "", i * 1370, 630, 1310, latest_notice, (void *)(uintptr_t)i);
        lv_obj_add_flag(ui.overview_notice[i], LV_OBJ_FLAG_HIDDEN);
    }
    home_refresh(NULL);
}

static void show_page(enum page page)
{
    if(ui.pending != NONE || ((ui.recording || ui.playing) && page != MEDIA)) return;
    if(ui.term_open) puts("terminal_live=0");
    ui.term_scroll = NULL;
    ui.term_open = false;
    ui.term_keyboard = false;
    ui.queued_key = NULL;
    ui.queued_submit = 0;
    ui.list_ready = false;
    ui.entry = ui.list = NULL;
    ui.sms_body = false;
    ui.dial_number[0] = 0;
    ui.composition = NULL;
    memset(ui.overview_notice, 0, sizeof(ui.overview_notice));
    ui.hero_clock = ui.hero_date = ui.home_wifi = ui.notice_hint = ui.media_clock = NULL;
    lv_obj_clean(ui.body);
    lv_label_set_text(ui.status, "");
    ui.page = page;
    set_shade(0);
    unsigned selected = page == PHONE || page == MISSED ? 1 : page == SMS ? 2 : page == TERMINAL ? 3 : 0;
    select_tab(selected);
    if(page == NETWORK) {
        show_overview();
    } else if(page == BLUETOOTH || page == MOBILE) {
        label(ui.body, page == BLUETOOTH ? tr("蓝牙设备", "Bluetooth devices") : tr("蜂窝数据", "Mobile data"), 30, 28);
        reading_area(140);
        send_request(DETAIL_BODY, page == BLUETOOTH ? "bt.devices" : "mobile.summary");
    } else if(page == WIFI) {
        dropdown(1770);
        button(ui.body, tr("扫描", "Scan"), 1810, 0, 350, network_scan, NULL);
        button(ui.body, tr("连接", "Connect"), 2200, 0, 500, wifi_join, NULL);
        ui.entry = entry(0, 130, 2700, 64, tr("密码（已保存或开放网络可留空）", "Password (leave blank for saved or open network)"));
        lv_textarea_set_password_mode(ui.entry, true);
        keyboard(ui.entry, 263);
    } else if(page == PHONE) {
        ui.entry = entry(0, 0, 1300, 21, tr("电话号码", "Phone number"));
        lv_textarea_set_accepted_chars(ui.entry, "+0123456789");
        ui.dial = button(ui.body, tr("拨号", "Dial"), 1340, 0, 410, dial, NULL);
        lv_obj_add_event_cb(ui.entry, dial_reset, LV_EVENT_VALUE_CHANGED, NULL);
        button(ui.body, tr("挂断", "Hang up"), 1790, 0, 430, action, "phone.hangup");
        button(ui.body, tr("状态", "Status"), 2260, 0, 440, action, "phone.status");
        button(ui.body, tr("未接来电", "Missed calls"), 0, 888, 540, tab, (void *)(uintptr_t)MISSED);
        static const char *const keys[] = {"1", "2", "3", "4", "5", "6", "\n",
                                           "7", "8", "9", "0", "+", LV_SYMBOL_BACKSPACE, ""};
        static const lv_buttonmatrix_ctrl_t flags[] = {
            LV_KEYBOARD_CTRL_BUTTON_FLAGS | 1, LV_KEYBOARD_CTRL_BUTTON_FLAGS | 1,
            LV_KEYBOARD_CTRL_BUTTON_FLAGS | 1, LV_KEYBOARD_CTRL_BUTTON_FLAGS | 1,
            LV_KEYBOARD_CTRL_BUTTON_FLAGS | 1, LV_KEYBOARD_CTRL_BUTTON_FLAGS | 1,
            LV_KEYBOARD_CTRL_BUTTON_FLAGS | 1, LV_KEYBOARD_CTRL_BUTTON_FLAGS | 1,
            LV_KEYBOARD_CTRL_BUTTON_FLAGS | 1, LV_KEYBOARD_CTRL_BUTTON_FLAGS | 1,
            LV_KEYBOARD_CTRL_BUTTON_FLAGS | 1, LV_KEYBOARD_CTRL_BUTTON_FLAGS | 1,
        };
        lv_obj_t *dialpad = keyboard(ui.entry, 170);
        lv_keyboard_set_map(dialpad, LV_KEYBOARD_MODE_USER_1, keys, flags);
        lv_keyboard_set_mode(dialpad, LV_KEYBOARD_MODE_USER_1);
    } else if(page == MISSED || page == SMS) {
        ui.detail = lv_obj_create(ui.body);
        lv_obj_set_pos(ui.detail, 0, 140);
        lv_obj_set_size(ui.detail, sx(2700), ui.body_height - 150);
        lv_obj_set_scroll_dir(ui.detail, LV_DIR_VER);
        if(page == MISSED) {
            button(ui.body, tr("刷新", "Refresh"), 0, 0, 450, show_missed, NULL);
            show_missed(NULL);
        } else {
            button(ui.body, tr("全部", "All"), 0, 0, 450, list_messages, NULL);
            button(ui.body, tr("未读", "Unread"), 490, 0, 450, list_messages, (void *)1);
            send_request(SMS_LIST, ui.sms_unread ? "sms.list\tunread" : "sms.list");
        }
    } else if(page == AUDIO) {
        label(ui.body, tr("扬声器", "Speaker"), 0, 55);
        label(ui.body, tr("铃声音量", "Ringtone"), 0, 285);
        ui.speaker = lv_slider_create(ui.body);
        ui.ring = lv_slider_create(ui.body);
        lv_obj_t *sliders[] = {ui.speaker, ui.ring};
        for(unsigned i = 0; i < 2; i++) {
            lv_obj_set_pos(sliders[i], sx(410), 45 + i * 230);
            lv_obj_set_size(sliders[i], sx(1080), 70);
            lv_slider_set_value(sliders[i], 50, LV_ANIM_OFF);
            lv_obj_t *value = label(ui.body, "50%", 1580, 55 + i * 230);
            lv_obj_add_event_cb(sliders[i], slider_label, LV_EVENT_VALUE_CHANGED, value);
        }
        button(ui.body, tr("设置扬声器", "Set speaker"), 1840, 24, 820, volume, "speaker.set");
        button(ui.body, tr("设置铃声", "Set ringtone"), 1840, 254, 820, volume, "ring.set");
        send_request(LEVELS, "audio.status");
    } else if(page == MEDIA) {
        show_media();
    } else if(page == TERMINAL) {
        show_terminal();
    } else {
        ui.entry = entry(0, 0, 2090, 256, tr("输入一行文字", "Type a line"));
        button(ui.body, ui.hardware_key ? tr("送入 TTY", "Send to TTY") : tr("返回文字", "Return text"),
               2130, 0, 570, finish_text, NULL);
        ui.typing_keys = keyboard(ui.entry, 155);
        if(ui.chinese)
            ui.ime_switch = button(ui.body, tr("中文拼音", "Pinyin"), 0, 884, 420, toggle_pinyin, NULL);
    }
}

static void tab(lv_event_t *event)
{
    show_page((enum page)(uintptr_t)lv_event_get_user_data(event));
}

static void add_tabs(void)
{
    const char *labels[] = {tr("总览", "Overview"), tr("电话", "Phone"), tr("短信", "SMS"), tr("终端", "Terminal")};
    const enum page pages[] = {NETWORK, PHONE, SMS, TERMINAL};
    for(unsigned i = 0; i < sizeof(labels) / sizeof(labels[0]); i++)
        ui.tabs[i] = button(ui.screen, labels[i], 90 + 510 * i, 170, 480, tab, (void *)(uintptr_t)pages[i]);
}

void panel_ui_start(lv_display_t *display, int socket_fd, const char *mode, void (*exit_panel)(void))
{
    ui.socket_fd = socket_fd;
    ui.leave = exit_panel;
    ui.hardware_key = strcmp(mode, "unlock") == 0;
    ui.display = display;
    ui.panel_unlocked = strcmp(mode, "start") == 0;
    ui.input_only = strcmp(mode, "input") == 0;
    ui.portrait = is_portrait(lv_display_get_rotation(display));
    ui.rotation_flip_pending = true;
    const char *font_path = V30_PANEL_FONT_PATH;
    lv_font_t *font = NULL;
    if(access(font_path, R_OK) == 0) {
        font = lv_freetype_font_create(font_path, LV_FREETYPE_FONT_RENDER_MODE_BITMAP, 48,
                                      LV_FREETYPE_FONT_STYLE_NORMAL);
    }
    ui.chinese = font != NULL;
    printf("panel_cjk_font=%u\n", ui.chinese);
    lv_theme_default_init(display, lv_color_hex(0x62c6ad), lv_color_hex(0x62c6ad),
                          true, font ? font : &lv_font_montserrat_36);
    build_screen();
    lv_timer_create(system_refresh, 1000, NULL);
    lv_timer_create(refresh_status, 10000, NULL);
    lv_timer_create(poll_media, 80, NULL);
    lv_timer_create(read_reply, 40, NULL);
    lv_timer_create(lookup_pinyin, 160, NULL);
    lv_timer_create(terminal_poll, 80, NULL);
    if(ui.hardware_key) {
        show_unlock();
    } else if(ui.input_only) {
        show_page(TEXT);
    } else {
        add_tabs();
        show_page(NETWORK);
    }
}


static void build_screen(void)
{
    lv_obj_t *screen = lv_screen_active();
    lv_obj_clean(screen);
    ui.entry = ui.composition = ui.list = NULL;
    ui.hero_clock = ui.hero_date = ui.home_wifi = ui.notice_hint = ui.media_clock = NULL;
    ui.screen = screen;
    memset(ui.tabs, 0, sizeof(ui.tabs));
    ui.shade = NULL;
    ui.body_height = lv_display_get_vertical_resolution(ui.display) - 423;
    lv_obj_remove_flag(screen, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_set_style_bg_color(screen, lv_color_hex(0x0d141a), 0);
    lv_obj_set_style_text_color(screen, lv_color_hex(0xe9eeec), 0);
    ui.bar = lv_obj_create(screen);
    lv_obj_remove_flag(ui.bar, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_set_size(ui.bar, lv_pct(100), 130);
    lv_obj_set_style_pad_all(ui.bar, 0, 0);
    lv_obj_set_style_radius(ui.bar, 0, 0);
    lv_obj_set_style_border_width(ui.bar, 0, 0);
    lv_obj_set_style_bg_color(ui.bar, lv_color_hex(0x111c24), 0);
    lv_obj_remove_flag(ui.bar, LV_OBJ_FLAG_GESTURE_BUBBLE);
    lv_obj_add_event_cb(ui.bar, shade_handle, LV_EVENT_GESTURE, NULL);
    lv_obj_add_event_cb(ui.bar, shade_handle, LV_EVENT_CLICKED, NULL);
    ui.clock = label(ui.bar, "", 90, 34);
    ui.notice_icons = label(ui.bar, "", 350, 34);
    ui.mic = label(ui.bar, LV_SYMBOL_AUDIO, 635, 34);
    lv_obj_set_style_text_font(ui.mic, &lv_font_montserrat_48, 0);
    lv_obj_set_style_text_color(ui.mic, lv_color_hex(0x8dd7bd), 0);
    lv_obj_add_flag(ui.mic, LV_OBJ_FLAG_HIDDEN);
    ui.signals = label(ui.bar, "", 0, 0);
    lv_obj_align(ui.signals, LV_ALIGN_RIGHT_MID, -sx(795), 0);
    ui.system_icons = label(ui.bar, "", 0, 0);
    lv_obj_align(ui.system_icons, LV_ALIGN_RIGHT_MID, -sx(100), 0);
    lv_obj_set_style_text_font(ui.notice_icons, &lv_font_montserrat_48, 0);
    lv_obj_set_style_text_font(ui.system_icons, &lv_font_montserrat_48, 0);
    system_refresh(NULL);
    button(screen, tr("返回 TTY", "Return to TTY"), 2180, 170, 610, leave, NULL);
    ui.status = label(screen, "", 90, 307);
    lv_obj_set_width(ui.status, sx(2700));
    lv_label_set_long_mode(ui.status, LV_LABEL_LONG_DOT);
    ui.body = lv_obj_create(screen);
    lv_obj_set_pos(ui.body, sx(90), 403);
    lv_obj_set_size(ui.body, sx(2700), ui.body_height);
    lv_obj_remove_flag(ui.body, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_set_style_pad_all(ui.body, 0, 0);
    lv_obj_set_style_border_width(ui.body, 0, 0);
    lv_obj_set_style_bg_opa(ui.body, LV_OPA_TRANSP, 0);
    build_shade();
}
