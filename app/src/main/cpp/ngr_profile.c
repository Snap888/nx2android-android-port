#include "ngr_profile.h"

#include <ctype.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>

#define NGR_JSON_MAX_TOKENS 65536u
#define NGR_JSON_MAX_DEPTH 64u

enum token_type { TOK_OBJECT, TOK_ARRAY, TOK_STRING, TOK_PRIMITIVE };

typedef struct {
    size_t start, end;
    int parent;
    enum token_type type;
} json_token;

typedef struct {
    const char *json;
    size_t length, position;
    json_token *tokens;
    size_t count, capacity;
    char *error;
    size_t error_capacity;
} json_parser;

static void set_error(char *out, size_t cap, const char *message) {
    if (out && cap) snprintf(out, cap, "%s", message ? message : "invalid JSON profile");
}

static int parser_error(json_parser *p, const char *message) {
    set_error(p->error, p->error_capacity, message);
    return -1;
}

static void skip_space(json_parser *p) {
    while (p->position < p->length) {
        char c = p->json[p->position];
        if (c == ' ' || c == '\t' || c == '\r' || c == '\n') p->position++;
        else break;
    }
}

static int token_new(json_parser *p, enum token_type type, size_t start, int parent) {
    if (p->count >= NGR_JSON_MAX_TOKENS) {
        parser_error(p, "profile JSON contains too many tokens");
        return -1;
    }
    if (p->count == p->capacity) {
        size_t next = p->capacity ? p->capacity * 2 : 128;
        if (next > NGR_JSON_MAX_TOKENS) next = NGR_JSON_MAX_TOKENS;
        json_token *grown = (json_token *)realloc(p->tokens, next * sizeof(*grown));
        if (!grown) {
            parser_error(p, "out of memory parsing profile JSON");
            return -1;
        }
        p->tokens = grown;
        p->capacity = next;
    }
    size_t index = p->count++;
    p->tokens[index] = (json_token){start, start, parent, type};
    return (int)index;
}

static int hex4(const char *s) {
    for (int i = 0; i < 4; ++i) if (!isxdigit((unsigned char)s[i])) return 0;
    return 1;
}

static int parse_string(json_parser *p, int parent) {
    if (p->position >= p->length || p->json[p->position] != '"') return parser_error(p, "expected JSON string");
    size_t quote = p->position++;
    int index = token_new(p, TOK_STRING, p->position, parent);
    if (index < 0) return -1;
    while (p->position < p->length) {
        unsigned char c = (unsigned char)p->json[p->position++];
        if (c == '"') {
            p->tokens[index].end = p->position - 1;
            return index;
        }
        if (c < 0x20) return parser_error(p, "control character in JSON string");
        if (c == '\\') {
            if (p->position >= p->length) return parser_error(p, "truncated JSON escape");
            char e = p->json[p->position++];
            if (e == '"' || e == '\\' || e == '/' || e == 'b' || e == 'f' || e == 'n' || e == 'r' || e == 't') continue;
            if (e == 'u') {
                if (p->length - p->position < 4 || !hex4(p->json + p->position))
                    return parser_error(p, "invalid Unicode escape in JSON string");
                p->position += 4;
                continue;
            }
            return parser_error(p, "invalid JSON string escape");
        }
    }
    p->position = quote;
    return parser_error(p, "unterminated JSON string");
}

static int primitive_valid(const char *s, size_t n) {
    if ((n == 4 && !memcmp(s, "true", 4)) ||
        (n == 5 && !memcmp(s, "false", 5)) ||
        (n == 4 && !memcmp(s, "null", 4))) return 1;
    size_t i = 0;
    if (i < n && s[i] == '-') i++;
    if (i >= n) return 0;
    if (s[i] == '0') i++;
    else {
        if (s[i] < '1' || s[i] > '9') return 0;
        while (i < n && isdigit((unsigned char)s[i])) i++;
    }
    if (i < n && s[i] == '.') {
        i++;
        size_t begin = i;
        while (i < n && isdigit((unsigned char)s[i])) i++;
        if (i == begin) return 0;
    }
    if (i < n && (s[i] == 'e' || s[i] == 'E')) {
        i++;
        if (i < n && (s[i] == '+' || s[i] == '-')) i++;
        size_t begin = i;
        while (i < n && isdigit((unsigned char)s[i])) i++;
        if (i == begin) return 0;
    }
    return i == n;
}

static int parse_value(json_parser *p, int parent, unsigned depth);

static int parse_array(json_parser *p, int parent, unsigned depth) {
    int index = token_new(p, TOK_ARRAY, p->position, parent);
    if (index < 0) return -1;
    p->position++;
    skip_space(p);
    if (p->position < p->length && p->json[p->position] == ']') {
        p->position++;
        p->tokens[index].end = p->position;
        return index;
    }
    for (;;) {
        if (parse_value(p, index, depth + 1) < 0) return -1;
        skip_space(p);
        if (p->position >= p->length) return parser_error(p, "unterminated JSON array");
        char c = p->json[p->position++];
        if (c == ']') break;
        if (c != ',') return parser_error(p, "expected comma in JSON array");
        skip_space(p);
    }
    p->tokens[index].end = p->position;
    return index;
}

static int parse_object(json_parser *p, int parent, unsigned depth) {
    int index = token_new(p, TOK_OBJECT, p->position, parent);
    if (index < 0) return -1;
    p->position++;
    skip_space(p);
    if (p->position < p->length && p->json[p->position] == '}') {
        p->position++;
        p->tokens[index].end = p->position;
        return index;
    }
    for (;;) {
        if (p->position >= p->length || p->json[p->position] != '"')
            return parser_error(p, "expected object key");
        if (parse_string(p, index) < 0) return -1;
        skip_space(p);
        if (p->position >= p->length || p->json[p->position++] != ':')
            return parser_error(p, "expected colon after object key");
        skip_space(p);
        if (parse_value(p, index, depth + 1) < 0) return -1;
        skip_space(p);
        if (p->position >= p->length) return parser_error(p, "unterminated JSON object");
        char c = p->json[p->position++];
        if (c == '}') break;
        if (c != ',') return parser_error(p, "expected comma in JSON object");
        skip_space(p);
    }
    p->tokens[index].end = p->position;
    return index;
}

static int parse_value(json_parser *p, int parent, unsigned depth) {
    if (depth > NGR_JSON_MAX_DEPTH) return parser_error(p, "profile JSON nesting is too deep");
    skip_space(p);
    if (p->position >= p->length) return parser_error(p, "unexpected end of JSON");
    char c = p->json[p->position];
    if (c == '{') return parse_object(p, parent, depth);
    if (c == '[') return parse_array(p, parent, depth);
    if (c == '"') return parse_string(p, parent);
    size_t start = p->position;
    while (p->position < p->length) {
        c = p->json[p->position];
        if (c == ',' || c == ']' || c == '}' || c == ' ' || c == '\t' || c == '\r' || c == '\n') break;
        p->position++;
    }
    size_t n = p->position - start;
    if (!n || !primitive_valid(p->json + start, n)) return parser_error(p, "invalid JSON primitive");
    int index = token_new(p, TOK_PRIMITIVE, start, parent);
    if (index < 0) return -1;
    p->tokens[index].end = p->position;
    return index;
}

static int parse_document(const char *json, size_t length, json_parser *p) {
    if (!json || !length) return parser_error(p, "empty JSON document");
    p->json = json;
    p->length = length;
    p->position = p->count = p->capacity = 0;
    p->tokens = NULL;
    int root = parse_value(p, -1, 0);
    if (root < 0) { free(p->tokens); p->tokens = NULL; return -1; }
    skip_space(p);
    if (p->position != p->length || root != 0 || p->tokens[root].type != TOK_OBJECT) {
        free(p->tokens); p->tokens = NULL;
        return parser_error(p, "JSON root must be one object with no trailing data");
    }
    return root;
}

static size_t next_token(const json_parser *p, size_t index) {
    size_t next = index + 1;
    while (next < p->count && p->tokens[next].start < p->tokens[index].end) next++;
    return next;
}

static int object_get(const json_parser *p, int object, const char *key) {
    if (object < 0 || (size_t)object >= p->count || p->tokens[object].type != TOK_OBJECT) return -1;
    size_t i = (size_t)object + 1;
    while (i < p->count && p->tokens[i].parent == object) {
        size_t value = i + 1;
        if (value >= p->count || p->tokens[value].parent != object) return -1;
        size_t n = p->tokens[i].end - p->tokens[i].start;
        if (p->tokens[i].type == TOK_STRING && n == strlen(key) &&
            !memcmp(p->json + p->tokens[i].start, key, n)) return (int)value;
        i = next_token(p, value);
    }
    return -1;
}

static size_t array_count(const json_parser *p, int array) {
    if (array < 0 || (size_t)array >= p->count || p->tokens[array].type != TOK_ARRAY) return 0;
    size_t count = 0, i = (size_t)array + 1;
    while (i < p->count && p->tokens[i].parent == array) { count++; i = next_token(p, i); }
    return count;
}

static int array_at(const json_parser *p, int array, size_t wanted) {
    if (array < 0 || (size_t)array >= p->count || p->tokens[array].type != TOK_ARRAY) return -1;
    size_t i = (size_t)array + 1, n = 0;
    while (i < p->count && p->tokens[i].parent == array) {
        if (n++ == wanted) return (int)i;
        i = next_token(p, i);
    }
    return -1;
}

static int token_text_eq(const json_parser *p, int token, const char *value) {
    if (token < 0 || (size_t)token >= p->count || (p->tokens[token].type != TOK_STRING && p->tokens[token].type != TOK_PRIMITIVE)) return 0;
    size_t n = p->tokens[token].end - p->tokens[token].start;
    return n == strlen(value) && !memcmp(p->json + p->tokens[token].start, value, n);
}

static int token_copy(const json_parser *p, int token, char *out, size_t cap) {
    if (token < 0 || (size_t)token >= p->count || p->tokens[token].type != TOK_STRING || !cap) return -1;
    size_t n = p->tokens[token].end - p->tokens[token].start;
    if (n >= cap || memchr(p->json + p->tokens[token].start, '\\', n)) return -1;
    memcpy(out, p->json + p->tokens[token].start, n);
    out[n] = 0;
    return (int)n;
}

static int is_hex_string(const char *s, size_t n) {
    if (strlen(s) != n) return 0;
    for (size_t i = 0; i < n; ++i) if (!isxdigit((unsigned char)s[i])) return 0;
    return 1;
}

static int required_string(const json_parser *p, int object, const char *key, char *out, size_t cap) {
    return token_copy(p, object_get(p, object, key), out, cap) > 0;
}

static int validate_string_array(const json_parser *p, int array, size_t max_count, size_t max_length, size_t *count_out) {
    if (array < 0 || p->tokens[array].type != TOK_ARRAY) return 0;
    size_t count = array_count(p, array);
    if (count > max_count) return 0;
    for (size_t i = 0; i < count; ++i) {
        int item = array_at(p, array, i);
        size_t n = p->tokens[item].end - p->tokens[item].start;
        if (p->tokens[item].type != TOK_STRING || !n || n > max_length) return 0;
    }
    if (count_out) *count_out = count;
    return 1;
}

static int validate_game_rows(const json_parser *p, int rows, size_t *count_out) {
    if (rows < 0 || p->tokens[rows].type != TOK_ARRAY) return 0;
    size_t count = array_count(p, rows);
    if (count > 512) return 0;
    for (size_t i = 0; i < count; ++i) {
        int row = array_at(p, rows, i);
        int key = object_get(p, row, "key");
        int values = object_get(p, row, "values");
        if (key < 0 || p->tokens[key].type != TOK_STRING || token_copy(p, key, (char[256]){0}, 256) <= 0) return 0;
        if (values < 0 || p->tokens[values].type != TOK_ARRAY || array_count(p, values) > 64) return 0;
        for (size_t k = 0; k < array_count(p, values); ++k) {
            int v = array_at(p, values, k);
            if (p->tokens[v].type != TOK_STRING || p->tokens[v].end - p->tokens[v].start > 4096) return 0;
        }
    }
    if (count_out) *count_out = count;
    return 1;
}

static int validate_tables(const json_parser *p, int tables, size_t *rows_out) {
    if (tables < 0 || p->tokens[tables].type != TOK_OBJECT) return 0;
    size_t total = 0, i = (size_t)tables + 1;
    while (i < p->count && p->tokens[i].parent == tables) {
        size_t value = i + 1;
        if (value >= p->count || p->tokens[value].parent != tables || p->tokens[value].type != TOK_ARRAY) return 0;
        size_t n = array_count(p, (int)value);
        if (n > 4096 || total > 4096 - n) return 0;
        total += n;
        for (size_t r = 0; r < n; ++r) {
            int row = array_at(p, (int)value, r);
            if (p->tokens[row].type != TOK_ARRAY || array_count(p, row) > 16) return 0;
            for (size_t k = 0; k < array_count(p, row); ++k) {
                int field = array_at(p, row, k);
                if (p->tokens[field].type != TOK_STRING || p->tokens[field].end - p->tokens[field].start > 512) return 0;
            }
        }
        i = next_token(p, value);
    }
    if (rows_out) *rows_out = total;
    return 1;
}

static int validate_overlay(const json_parser *p, int android, size_t *count_out) {
    int overlay = object_get(p, android, "overlay");
    if (overlay < 0 || p->tokens[overlay].type != TOK_ARRAY) return 0;
    size_t count = array_count(p, overlay);
    if (count > 128) return 0;
    for (size_t i = 0; i < count; ++i) {
        int row = array_at(p, overlay, i);
        char value[256];
        if (!required_string(p, row, "layout", value, sizeof(value)) ||
            !required_string(p, row, "name", value, sizeof(value)) ||
            !required_string(p, row, "kind", value, sizeof(value))) return 0;
    }
    if (count_out) *count_out = count;
    return 1;
}

int ngr_profile_validate(const char *profile_json, size_t profile_size,
                         const char *manifest_json, size_t manifest_size,
                         const char *expected_game_id,
                         ngr_profile_summary *summary,
                         char *error_out, size_t error_capacity) {
    json_parser profile = {0}, manifest = {0};
    profile.error = error_out; profile.error_capacity = error_capacity;
    manifest.error = error_out; manifest.error_capacity = error_capacity;
    int result = -1;
    ngr_profile_summary local = {0};
    if (parse_document(profile_json, profile_size, &profile) < 0) goto done;
    if (parse_document(manifest_json, manifest_size, &manifest) < 0) goto done;

    int schema = object_get(&profile, 0, "schema_version");
    if (schema < 0 || profile.tokens[schema].type != TOK_PRIMITIVE ||
        !token_text_eq(&profile, schema, "1")) { set_error(error_out, error_capacity, "unsupported profile schema_version"); goto done; }

    int identity = object_get(&profile, 0, "identity");
    int source = object_get(&profile, 0, "source");
    int game = object_get(&profile, 0, "game");
    int manifest_title = object_get(&manifest, 0, "title_id");
    int manifest_hash = object_get(&manifest, 0, "profile_h");
    int manifest_game_id = object_get(&manifest, 0, "game_id");
    if (identity < 0 || source < 0 || game < 0 || manifest_title < 0 || manifest_hash < 0 || manifest_game_id < 0) {
        set_error(error_out, error_capacity, "profile or data manifest is missing required objects");
        goto done;
    }
    if (!required_string(&profile, identity, "title_id", local.title_id, sizeof(local.title_id)) ||
        !is_hex_string(local.title_id, 16)) { set_error(error_out, error_capacity, "profile identity.title_id is invalid"); goto done; }
    char manifest_id[32], manifest_profile_hash[80];
    if (token_copy(&manifest, manifest_title, manifest_id, sizeof(manifest_id)) < 0 ||
        strcasecmp(local.title_id, manifest_id)) { set_error(error_out, error_capacity, "profile title_id does not match nx2a-data.json"); goto done; }
    char packed_game_id[32], profile_library_id[32];
    if (!expected_game_id || strlen(expected_game_id) != 20 ||
        token_copy(&manifest, manifest_game_id, packed_game_id, sizeof(packed_game_id)) < 0 ||
        strcmp(expected_game_id, packed_game_id) ||
        !required_string(&profile, identity, "library_id", profile_library_id, sizeof(profile_library_id)) ||
        strcmp(expected_game_id, profile_library_id)) {
        set_error(error_out, error_capacity, "profile library ID does not match the selected NGR shortcut");
        goto done;
    }
    if (!required_string(&profile, source, "game_profile_sha256", local.game_profile_sha256, sizeof(local.game_profile_sha256)) ||
        !is_hex_string(local.game_profile_sha256, 64) ||
        token_copy(&manifest, manifest_hash, manifest_profile_hash, sizeof(manifest_profile_hash)) < 0 ||
        strcasecmp(local.game_profile_sha256, manifest_profile_hash)) {
        set_error(error_out, error_capacity, "profile game_profile_sha256 does not match nx2a-data.json.profile_h");
        goto done;
    }

    int modules = object_get(&profile, game, "modules");
    if (!validate_string_array(&profile, modules, 64, 255, &local.module_count) || !local.module_count) {
        set_error(error_out, error_capacity, "game.modules must contain 1..64 non-empty strings");
        goto done;
    }
    int rows = object_get(&profile, game, "rows");
    if (!validate_game_rows(&profile, rows, &local.profile_row_count)) {
        set_error(error_out, error_capacity, "game.rows is invalid or exceeds limits");
        goto done;
    }
    int tables = object_get(&profile, game, "tables");
    if (!validate_tables(&profile, tables, &local.game_table_row_count)) {
        set_error(error_out, error_capacity, "game.tables is invalid or exceeds limits");
        goto done;
    }

    int android = object_get(&profile, 0, "android");
    if (android < 0) { set_error(error_out, error_capacity, "profile.android is missing"); goto done; }
    if (profile.tokens[android].type == TOK_OBJECT) {
        int overlay = object_get(&profile, android, "overlay");
        if (!validate_overlay(&profile, android, &local.overlay_count)) {
            set_error(error_out, error_capacity, "android.overlay is invalid or exceeds 128 controls");
            goto done;
        }
        (void)overlay;
        int env = object_get(&profile, android, "env");
        int requires = object_get(&profile, android, "requires");
        if (!validate_string_array(&profile, env, 256, 4096, NULL) ||
            !validate_string_array(&profile, requires, 32, 64, NULL)) {
            set_error(error_out, error_capacity, "android env/requires arrays are invalid");
            goto done;
        }
        int settings = object_get(&profile, android, "settings");
        if (settings < 0 || profile.tokens[settings].type != TOK_OBJECT) {
            set_error(error_out, error_capacity, "android.settings must be an object");
            goto done;
        }
    } else if (profile.tokens[android].type != TOK_PRIMITIVE || !token_text_eq(&profile, android, "null")) {
        set_error(error_out, error_capacity, "profile.android must be an object or null");
        goto done;
    }

    local.schema_version = 1;
    if (summary) *summary = local;
    set_error(error_out, error_capacity, "");
    result = 0;

done:
    free(profile.tokens);
    free(manifest.tokens);
    return result;
}
