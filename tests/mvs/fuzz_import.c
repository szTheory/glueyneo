/* SPDX-License-Identifier: MIT */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "glueyneo/glueyneo.h"

#define MAX_INPUT ((size_t)64u * 1024u * 1024u)
#define MUTATIONS 48u

int mvs_import_memory(const uint8_t *zip, size_t zip_size,
                      uint8_t **out_bundle, size_t *out_size);

static void exercise(const uint8_t *bytes, size_t length) {
    uint8_t *bundle = NULL;
    size_t bundle_size = 0u;
    (void)mvs_import_memory(bytes, length, &bundle, &bundle_size);
    free(bundle);
}

static uint32_t be32(const uint8_t *p) {
    return (uint32_t)p[0] << 24 | (uint32_t)p[1] << 16 | (uint32_t)p[2] << 8 | p[3];
}

static int load_audio(gn_instance *instance, const uint8_t *bytes, size_t size) {
    if (size < 16 || memcmp(bytes, "GNMV", 4) || be32(bytes+4) != GN_MVS_MANIFEST_VERSION_ZOOM ||
        be32(bytes+8) != GN_MVS_PROFILE_MSX || be32(bytes+12) != 8) return 0;
    gn_mvs_manifest_v3 m;
    memset(&m, 0, sizeof(m));
    m.version = GN_MVS_MANIFEST_VERSION_ZOOM; m.profile = GN_MVS_PROFILE_MSX; m.region_count = 8;
    size_t at = 16;
    for (size_t i = 0; i < 8; ++i) {
        if (at > size || size-at < 12) return 0;
        const uint32_t role=be32(bytes+at), high=be32(bytes+at+4), n=be32(bytes+at+8);
        at += 12;
        if (role != i+1 || high || !n || n > size-at) return 0;
        m.regions[i]=(gn_mvs_region){(gn_mvs_region_role)role,bytes+at,n,n,GN_MVS_LAYOUT_LINEAR};
        at += n;
    }
    return at == size && gn_load_mvs_v3(instance, &m) == GN_STATUS_OK;
}

/* Fixed original seed/call corpus. No invalid foreign pointer is dereferenced:
 * pointer mutations use NULL, aligned owned storage, or an owned overlap. */
static int audio_calls(const char *path) {
    int ok=0;
    unsigned success=0, rejected=0;
    FILE *file=fopen(path,"rb");
    uint8_t *bytes=NULL;
    gn_instance *a=NULL,*b=NULL;
    uint32_t *pa=NULL,*pb=NULL;
    int16_t *aa=NULL,*ab=NULL;
    enum { WIDTH=320, HEIGHT=224, SAMPLES=GN_MVS_AUDIO_CAPACITY_FRAMES_V1*2 };
    const size_t pixel_bytes=(size_t)WIDTH*HEIGHT*sizeof(uint32_t);
    if (!file) goto done;
    if (fseek(file,0,SEEK_END)) goto done;
    const long measured=ftell(file);
    if (measured < 16 || (unsigned long)measured > GN_MVS_MAX_MEDIA_BYTES+112 ||
        fseek(file,0,SEEK_SET)) goto done;
    bytes=malloc((size_t)measured);
    if (!bytes || fread(bytes,1,(size_t)measured,file)!=(size_t)measured || fgetc(file)!=EOF) goto done;
    if (fclose(file)) { file=NULL; goto done; }
    file=NULL;
    if (gn_create(&a)!=GN_STATUS_OK || gn_create(&b)!=GN_STATUS_OK ||
        !load_audio(a,bytes,(size_t)measured) || !load_audio(b,bytes,(size_t)measured)) goto done;
    pa=malloc(pixel_bytes+2*sizeof(*pa)); pb=malloc(pixel_bytes+2*sizeof(*pb));
    aa=malloc((SAMPLES+2)*sizeof(*aa)); ab=malloc((SAMPLES+2)*sizeof(*ab));
    if (!pa || !pb || !aa || !ab) goto done;
    const gn_mvs_frame_request_v1 normal={GN_MVS_FRAME_REQUEST_V1_VERSION,0,GN_PIXEL_XRGB8888,
        WIDTH,HEIGHT,WIDTH*sizeof(uint32_t),(uint8_t *)(pa+1),pixel_bytes,aa+1,GN_MVS_AUDIO_CAPACITY_FRAMES_V1};
    /* Establish actual output before any mutation; import-only/no-op execution
     * cannot supply the success denominator. Both fresh machines must agree. */
    gn_mvs_frame_request_v1 baseline=normal;
    baseline.pixels=(uint8_t *)(pb+1); baseline.audio=ab+1;
    gn_mvs_frame_result_v1 initial_a,initial_b;
    memset(&initial_a,0,sizeof(initial_a)); memset(&initial_b,0,sizeof(initial_b));
    if (gn_mvs_advance_frame_v1(a,&normal,sizeof(normal),&initial_a,sizeof(initial_a))!=GN_STATUS_OK ||
        gn_mvs_advance_frame_v1(b,&baseline,sizeof(baseline),&initial_b,sizeof(initial_b))!=GN_STATUS_OK ||
        !initial_a.audio_frames_delivered ||
        initial_a.audio_frames_delivered>GN_MVS_AUDIO_CAPACITY_FRAMES_V1 ||
        memcmp(&initial_a,&initial_b,sizeof(initial_a)) || memcmp(pa+1,pb+1,pixel_bytes) ||
        memcmp(aa+1,ab+1,initial_a.audio_frames_delivered*2*sizeof(*aa))) goto done;
    success+=2;
    for (unsigned i=0; i<14; ++i) {
        memset(pa,0x5a,pixel_bytes+2*sizeof(*pa));
        memset(aa,0x5a,(SAMPLES+2)*sizeof(*aa));
        gn_mvs_frame_request_v1 bad=normal;
        size_t request_bytes=sizeof(bad), result_bytes=sizeof(gn_mvs_frame_result_v1);
        switch(i%10) {
            case 0: bad.version=0; break;
            case 1: bad.input_mask=UINT32_C(0x80000000); break;
            case 2: --request_bytes; break;
            case 3: --result_bytes; break;
            case 4: --bad.audio_capacity_frames; break;
            case 5: bad.audio=NULL; break;
            case 6: bad.pixels=NULL; break;
            case 7: bad.pitch_bytes=1; break;
            case 8: bad.audio=(int16_t *)(pa+1); break;
            default: bad.pixel_capacity_bytes=1; break;
        }
        struct guarded_result { uint64_t before; gn_mvs_frame_result_v1 result; uint64_t after; } gr, saved;
        memset(&gr,0x5a,sizeof(gr)); memcpy(&saved,&gr,sizeof(gr));
        if (gn_mvs_advance_frame_v1(a,&bad,request_bytes,&gr.result,result_bytes)==GN_STATUS_OK ||
            memcmp(&gr,&saved,sizeof(gr))) goto done;
        const uint8_t *pixels=(const uint8_t *)pa, *audio=(const uint8_t *)aa;
        for (size_t n=0; n<pixel_bytes+2*sizeof(*pa); ++n) if (pixels[n]!=0x5a) goto done;
        for (size_t n=0; n<(SAMPLES+2)*sizeof(*aa); ++n) if (audio[n]!=0x5a) goto done;
        ++rejected;
        gn_mvs_frame_request_v1 ra=normal, rb=normal;
        ra.input_mask=rb.input_mask=(i%3==2 ? GN_MVS_INPUT_P1_A : 0);
        rb.pixels=(uint8_t *)(pb+1); rb.audio=ab+1;
        memset(pb,0x5a,pixel_bytes+2*sizeof(*pb)); memset(ab,0x5a,(SAMPLES+2)*sizeof(*ab));
        gn_mvs_frame_result_v1 ar,br;
        memset(&ar,0,sizeof(ar)); memset(&br,0,sizeof(br));
        if (gn_mvs_advance_frame_v1(a,&ra,sizeof(ra),&ar,sizeof(ar))!=GN_STATUS_OK ||
            gn_mvs_advance_frame_v1(b,&rb,sizeof(rb),&br,sizeof(br))!=GN_STATUS_OK ||
            ar.audio_frames_generated==0 || ar.audio_frames_generated>GN_MVS_AUDIO_CAPACITY_FRAMES_V1 ||
            ar.audio_frames_delivered!=ar.audio_frames_generated ||
            memcmp(&ar,&br,sizeof(ar)) || memcmp(pa,pb,pixel_bytes+2*sizeof(*pa)) ||
            memcmp(aa,ab,(SAMPLES+2)*sizeof(*aa)) ||
            pa[0]!=UINT32_C(0x5a5a5a5a) || pa[WIDTH*HEIGHT+1]!=UINT32_C(0x5a5a5a5a) ||
            aa[0]!=INT16_C(0x5a5a) || aa[SAMPLES+1]!=INT16_C(0x5a5a)) goto done;
        success+=2;
        if (i==4) {
            if (gn_reset(a)!=GN_STATUS_OK || gn_reset(b)!=GN_STATUS_OK) goto done;
        } else if(i==8) {
            if (gn_unload(a)!=GN_STATUS_OK || gn_unload(b)!=GN_STATUS_OK ||
                !load_audio(a,bytes,(size_t)measured) || !load_audio(b,bytes,(size_t)measured)) goto done;
        } else if(i==10) {
            ra.audio=rb.audio=NULL; ra.audio_capacity_frames=rb.audio_capacity_frames=0;
            if (gn_mvs_advance_frame_v1(a,&ra,sizeof(ra),&ar,sizeof(ar))!=GN_STATUS_OK ||
                gn_mvs_advance_frame_v1(b,&rb,sizeof(rb),&br,sizeof(br))!=GN_STATUS_OK ||
                !ar.audio_frames_generated || ar.audio_frames_delivered ||
                ar.audio_frames_discarded!=ar.audio_frames_generated || memcmp(&ar,&br,sizeof(ar))) goto done;
            success+=2;
        }
    }
    printf("MVS_AUDIO_CALLS success=%u rejected=%u seed=51a7c0de\n",success,rejected);
    ok=success>0 && rejected>0;
done:
    if(file) fclose(file);
    gn_destroy(a); gn_destroy(b);
    free(bytes); free(pa); free(pb); free(aa); free(ab);
    if(!ok) fprintf(stderr,"native audio call corpus failed\n");
    return ok ? 0 : 1;
}

int main(int argc, char **argv) {
    if (argc==3 && strcmp(argv[1],"--audio-calls")==0) return audio_calls(argv[2]);
    if (argc != 2) return 2;
    FILE *file = fopen(argv[1], "rb");
    if (file == NULL || fseek(file, 0, SEEK_END) != 0) {
        if (file != NULL) fclose(file);
        return 2;
    }
    const long size = ftell(file);
    if (size < 0 || (unsigned long)size > MAX_INPUT || fseek(file, 0, SEEK_SET) != 0) {
        fclose(file);
        return 2;
    }
    uint8_t *bytes = (uint8_t *)malloc((size_t)size);
    if (bytes == NULL || fread(bytes, 1u, (size_t)size, file) != (size_t)size) {
        free(bytes); fclose(file); return 2;
    }
    fclose(file);
    exercise(bytes, (size_t)size);
    uint32_t state = UINT32_C(0x51a7c0de);
    for (size_t iteration = 0u; iteration < MUTATIONS && size > 0; ++iteration) {
        state ^= state << 13; state ^= state >> 17; state ^= state << 5;
        const size_t offset = (size_t)state % (size_t)size;
        const uint8_t previous = bytes[offset];
        bytes[offset] ^= (uint8_t)(1u << (state & 7u));
        exercise(bytes, (size_t)size);
        bytes[offset] = previous;
    }
    free(bytes);
    return 0;
}
