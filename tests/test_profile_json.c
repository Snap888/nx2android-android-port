#include "ngr_profile.h"

#include <assert.h>
#include <stdio.h>
#include <string.h>

static const char *profile_json =
    "{"
    "\"schema_version\":1,"
    "\"identity\":{\"title_id\":\"0100000000001000\",\"library_id\":\"1234567890abcdef1234\"},"
    "\"source\":{\"game_profile_sha256\":\"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\"},"
    "\"game\":{"
      "\"modules\":[\"main\",\"sdk\"],"
      "\"rows\":[{\"key\":\"modules\",\"values\":[\"main\",\"sdk\"]}],"
      "\"tables\":{\"fps_locks.tsv\":[[\"0123456789abcdef0123456789abcdef\",\"main\",\"0x10\"]]}"
    "},"
    "\"android\":{"
      "\"overlay\":[{\"layout\":\"tablet\",\"name\":\"menu\",\"kind\":\"menu\"}],"
      "\"env\":[\"DM_LANG=en-US\"],"
      "\"requires\":[],"
      "\"settings\":{\"overlay\":\"1\"}"
    "}"
    "}";

static const char *manifest_json =
    "{\"title_id\":\"0100000000001000\","
    "\"game_id\":\"1234567890abcdef1234\","
    "\"profile_h\":\"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\"}";

int main(void) {
    ngr_profile_summary summary;
    char error[256] = {0};
    const char *selected_id = "1234567890abcdef1234";
    int rc = ngr_profile_validate(profile_json, strlen(profile_json),
                                  manifest_json, strlen(manifest_json),
                                  selected_id, &summary, error, sizeof(error));
    if (rc) fprintf(stderr, "valid profile rejected: %s\n", error);
    assert(rc == 0);
    assert(summary.schema_version == 1);
    assert(!strcmp(summary.title_id, "0100000000001000"));
    assert(summary.module_count == 2);
    assert(summary.profile_row_count == 1);
    assert(summary.game_table_row_count == 1);
    assert(summary.overlay_count == 1);

    const char *bad_manifest =
        "{\"title_id\":\"0100000000001000\","
        "\"game_id\":\"1234567890abcdef1234\","
        "\"profile_h\":\"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\"}";
    rc = ngr_profile_validate(profile_json, strlen(profile_json),
                              bad_manifest, strlen(bad_manifest),
                              selected_id, &summary, error, sizeof(error));
    assert(rc != 0);
    assert(strstr(error, "does not match") != NULL);

    const char *wrong_game =
        "{\"title_id\":\"0100000000001000\","
        "\"game_id\":\"aaaaaaaaaaaaaaaaaaaa\","
        "\"profile_h\":\"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\"}";
    rc = ngr_profile_validate(profile_json, strlen(profile_json),
                              wrong_game, strlen(wrong_game),
                              selected_id, &summary, error, sizeof(error));
    assert(rc != 0);
    assert(strstr(error, "library ID") != NULL);

    const char *bad_schema =
        "{\"schema_version\":2,\"identity\":{},\"source\":{},\"game\":{},\"android\":null}";
    rc = ngr_profile_validate(bad_schema, strlen(bad_schema),
                              manifest_json, strlen(manifest_json),
                              selected_id, &summary, error, sizeof(error));
    assert(rc != 0);
    assert(strstr(error, "schema_version") != NULL);

    const char *bad_json = "{\"schema_version\":1,";
    rc = ngr_profile_validate(bad_json, strlen(bad_json),
                              manifest_json, strlen(manifest_json),
                              selected_id, &summary, error, sizeof(error));
    assert(rc != 0);

    puts("NGR profile JSON validator tests passed");
    return 0;
}
