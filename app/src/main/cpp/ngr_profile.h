#ifndef NGR_PROFILE_H
#define NGR_PROFILE_H

#include <stddef.h>

typedef struct {
    int schema_version;
    char title_id[17];
    char game_profile_sha256[65];
    size_t module_count;
    size_t profile_row_count;
    size_t game_table_row_count;
    size_t overlay_count;
} ngr_profile_summary;

/* Validates schema v1 and binds profile.json to nx2a-data.json.profile_h.
 * Returns 0 on success, -1 with a readable error in error_out otherwise. */
int ngr_profile_validate(const char *profile_json, size_t profile_size,
                         const char *manifest_json, size_t manifest_size,
                         ngr_profile_summary *summary,
                         char *error_out, size_t error_capacity);

#endif
