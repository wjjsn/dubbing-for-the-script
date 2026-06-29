"""
DaVinci Resolve FCP XML 时间线生成器

用法:
    单文件: python -m src.timeline_generator scripts/sample.yaml
    批量:   python -m src.timeline_generator --all
"""

import math
import os
import re
import struct
import glob
import yaml
import xml.etree.ElementTree as ET
from xml.dom import minidom
from urllib.parse import quote

TIMEBASE = 24
TC_OFFSET = 86400
ASSET_DIR = "asset"
VOICE_DIR = "voice"
OUTPUT_DIR = "timeline"
WIN_BASE = "C:/Users/wjjsn/Desktop/new"


def _sanitize(s, max_len=50):
    s = re.sub(r'\s+', '', s)[:max_len]
    s = re.sub(r'[\\/:*?"<>|]', '', s)
    return s or "empty"


def _url_path(rel_path):
    full = f"{WIN_BASE}/{rel_path}"
    encoded = '/'.join(quote(p, safe='') for p in full.split('/'))
    encoded = encoded.replace('%3A', ':')
    return f"file://localhost/{encoded}"


def get_audio_duration_frames(wav_path):
    with open(wav_path, 'rb') as f:
        riff = f.read(4)
        if riff != b'RIFF':
            raise ValueError(f"Not a WAV file: {wav_path}")
        f.read(4)  # file size
        wave = f.read(4)
        if wave != b'WAVE':
            raise ValueError(f"Not a WAV file: {wav_path}")
        sample_rate = channels = bits_per_sample = data_size = 0
        while True:
            chunk_id = f.read(4)
            if len(chunk_id) < 4:
                break
            chunk_size = struct.unpack('<I', f.read(4))[0]
            if chunk_id == b'fmt ':
                fmt = f.read(chunk_size)
                audio_format = struct.unpack('<H', fmt[0:2])[0]
                channels = struct.unpack('<H', fmt[2:4])[0]
                sample_rate = struct.unpack('<I', fmt[4:8])[0]
                bits_per_sample = struct.unpack('<H', fmt[14:16])[0]
            elif chunk_id == b'data':
                data_size = chunk_size
                break
            else:
                f.seek(chunk_size, 1)
        bytes_per_sample = bits_per_sample // 8
        total_samples = data_size // (channels * bytes_per_sample)
        return math.ceil(total_samples / sample_rate * TIMEBASE)


def find_audio_file(voice_dir, index, character):
    if not os.path.isdir(voice_dir):
        return None
    prefix = f"{index:04d}-{character}-"
    for f in sorted(os.listdir(voice_dir)):
        if f.startswith(prefix) and f.endswith('.wav'):
            return os.path.join(voice_dir, f)
    return None


def find_character_image(character):
    for ext in ('.png', '.jpg', '.jpeg'):
        p = os.path.join(ASSET_DIR, f"{character}{ext}")
        if os.path.exists(p):
            return p
    return None


def collect_clips(yaml_path):
    with open(yaml_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    title = data.get("title", "untitled")
    script = data.get("script", [])
    voice_dir = os.path.join(VOICE_DIR, _sanitize(title))
    clips = []
    for i, item in enumerate(script):
        character = item.get("character", "旁白")
        text = item.get("text", "").strip()
        if not text:
            continue
        wav_path = find_audio_file(voice_dir, i, character)
        if not wav_path:
            print(f"  [跳过] [{i:04d}] {character}: 音频不存在")
            continue
        duration = get_audio_duration_frames(wav_path)
        img_path = find_character_image(character)
        clips.append({
            'index': i, 'character': character, 'text': text,
            'wav_path': wav_path,
            'wav_name': os.path.basename(wav_path),
            'img_path': img_path,
            'img_name': os.path.basename(img_path) if img_path else None,
            'duration': duration,
        })
    cursor = 0
    for c in clips:
        c['start'] = cursor
        c['end'] = cursor + c['duration']
        cursor = c['end']
    return title, clips


def _group_video_segments(clips):
    if not clips:
        return []
    segments, cur = [], None
    for c in clips:
        if not c['img_path']:
            continue
        if cur and c['character'] == cur['character'] and c['start'] == cur['end']:
            cur['end'] = c['end']
        else:
            if cur:
                segments.append(cur)
            cur = {'character': c['character'], 'img_path': c['img_path'],
                   'img_name': c['img_name'], 'start': c['start'], 'end': c['end']}
    if cur:
        segments.append(cur)
    return segments


# ── XML 构建辅助 ────────────────────────────────────────────


def _el(tag, text=None, attrib=None):
    el = ET.Element(tag, attrib or {})
    if text is not None:
        el.text = str(text)
    return el


def _add(parent, tag, text=None, attrib=None):
    el = _el(tag, text, attrib)
    parent.append(el)
    return el


def _rate(parent, timebase=TIMEBASE):
    r = _add(parent, 'rate')
    _add(r, 'timebase', timebase)
    _add(r, 'ntsc', 'FALSE')
    return r


def _filter_motion(parent, d):
    f = _add(parent, 'filter')
    _add(f, 'enabled', 'TRUE')
    _add(f, 'start', 0)
    _add(f, 'end', d)
    eff = _add(f, 'effect')
    _add(eff, 'name', 'Basic Motion')
    _add(eff, 'effectid', 'basic')
    _add(eff, 'effecttype', 'motion')
    _add(eff, 'mediatype', 'video')
    _add(eff, 'effectcategory', 'motion')
    for name, pid, val, vmin, vmax in [
        ('Scale', 'scale', 100, 1, 10000),
        ('Rotation', 'rotation', 0, -100000, 100000),
    ]:
        p = _add(eff, 'parameter')
        _add(p, 'name', name)
        _add(p, 'parameterid', pid)
        _add(p, 'value', val)
        _add(p, 'valuemin', vmin)
        _add(p, 'valuemax', vmax)
    for name, pid in [('Center', 'center'), ('Anchor Point', 'centerOffset')]:
        p = _add(eff, 'parameter')
        _add(p, 'name', name)
        _add(p, 'parameterid', pid)
        v = _add(p, 'value')
        _add(v, 'horiz', 0)
        _add(v, 'vert', 0)


def _filter_crop(parent, d):
    f = _add(parent, 'filter')
    _add(f, 'enabled', 'TRUE')
    _add(f, 'start', 0)
    _add(f, 'end', d)
    eff = _add(f, 'effect')
    _add(eff, 'name', 'Crop')
    _add(eff, 'effectid', 'crop')
    _add(eff, 'effecttype', 'motion')
    _add(eff, 'mediatype', 'video')
    _add(eff, 'effectcategory', 'motion')
    for name in ['left', 'right', 'top', 'bottom']:
        p = _add(eff, 'parameter')
        _add(p, 'name', name)
        _add(p, 'parameterid', name)
        _add(p, 'value', 0)
        _add(p, 'valuemin', 0)
        _add(p, 'valuemax', 100)


def _filter_opacity(parent, d):
    f = _add(parent, 'filter')
    _add(f, 'enabled', 'TRUE')
    _add(f, 'start', 0)
    _add(f, 'end', d)
    eff = _add(f, 'effect')
    _add(eff, 'name', 'Opacity')
    _add(eff, 'effectid', 'opacity')
    _add(eff, 'effecttype', 'motion')
    _add(eff, 'mediatype', 'video')
    _add(eff, 'effectcategory', 'motion')
    p = _add(eff, 'parameter')
    _add(p, 'name', 'opacity')
    _add(p, 'parameterid', 'opacity')
    _add(p, 'value', 100)
    _add(p, 'valuemin', 0)
    _add(p, 'valuemax', 100)


def _filter_timeremap(parent, d):
    f = _add(parent, 'filter')
    _add(f, 'enabled', 'TRUE')
    _add(f, 'start', -1)
    _add(f, 'end', -1)
    eff = _add(f, 'effect')
    _add(eff, 'name', 'Time Remap')
    _add(eff, 'effectid', 'timeremap')
    _add(eff, 'effecttype', 'motion')
    _add(eff, 'mediatype', 'video')
    _add(eff, 'effectcategory', 'motion')
    for name, pid, val in [('speed', 'speed', 0), ('variablespeed', 'variablespeed', 0)]:
        p = _add(eff, 'parameter')
        _add(p, 'name', name)
        _add(p, 'parameterid', pid)
        _add(p, 'value', val)
        _add(p, 'valuemin', -10000 if name == 'speed' else 0)
        _add(p, 'valuemax', 10000 if name == 'speed' else 1)
    for name, pid in [('reverse', 'reverse'), ('frameblending', 'frameblending')]:
        p = _add(eff, 'parameter')
        _add(p, 'name', name)
        _add(p, 'parameterid', pid)
        _add(p, 'value', 'FALSE')
    p = _add(eff, 'parameter')
    _add(p, 'name', 'graphdict')
    _add(p, 'parameterid', 'graphdict')
    for when, value, flags in [
        (0, 0, [('speedvirtualkf', 'TRUE'), ('speedkfstart', 'TRUE')]),
        (TC_OFFSET, 0, [('speedvirtualkf', 'TRUE'), ('speedkfin', 'TRUE')]),
        (TC_OFFSET + d, 0, [('speedvirtualkf', 'TRUE'), ('speedkfout', 'TRUE')]),
        (1440001, 1, [('speedvirtualkf', 'TRUE'), ('speedkfend', 'TRUE')]),
    ]:
        kf = _add(p, 'keyframe')
        _add(kf, 'when', when)
        _add(kf, 'value', value)
        for tag, val in flags:
            _add(kf, tag, val)
    _add(p, 'valuemin', 0)
    _add(p, 'valuemax', 0)
    interp = _add(p, 'interpolation')
    _add(interp, 'name', 'FCPCurve')


def _filter_audio_levels(parent, d):
    f = _add(parent, 'filter')
    _add(f, 'enabled', 'TRUE')
    _add(f, 'start', 0)
    _add(f, 'end', d)
    eff = _add(f, 'effect')
    _add(eff, 'name', 'Audio Levels')
    _add(eff, 'effectid', 'audiolevels')
    _add(eff, 'effecttype', 'audiolevels')
    _add(eff, 'mediatype', 'audio')
    _add(eff, 'effectcategory', 'audiolevels')
    p = _add(eff, 'parameter')
    _add(p, 'name', 'Level')
    _add(p, 'parameterid', 'level')
    _add(p, 'value', 1)
    _add(p, 'valuemin', '1e-05')
    _add(p, 'valuemax', '31.6228')


def _filter_audio_pan(parent, d):
    f = _add(parent, 'filter')
    _add(f, 'enabled', 'TRUE')
    _add(f, 'start', 0)
    _add(f, 'end', d)
    eff = _add(f, 'effect')
    _add(eff, 'name', 'Audio Pan')
    _add(eff, 'effectid', 'audiopan')
    _add(eff, 'effecttype', 'audiopan')
    _add(eff, 'mediatype', 'audio')
    _add(eff, 'effectcategory', 'audiopan')
    p = _add(eff, 'parameter')
    _add(p, 'name', 'Pan')
    _add(p, 'parameterid', 'pan')
    _add(p, 'value', 0)
    _add(p, 'valuemin', -1)
    _add(p, 'valuemax', 1)


# ── 片段构建 ────────────────────────────────────────────────


def _build_video_clipitem(seg, clip_idx, file_defs, file_refs):
    d = seg['end'] - seg['start']
    img_name = seg['img_name']
    clip = _el('clipitem', attrib={'id': f"{img_name} {clip_idx}"})
    _add(clip, 'name', img_name)
    _add(clip, 'duration', 1440001)
    _rate(clip)
    _add(clip, 'start', seg['start'])
    _add(clip, 'end', seg['end'])
    _add(clip, 'enabled', 'TRUE')
    _add(clip, 'in', TC_OFFSET)
    _add(clip, 'out', TC_OFFSET + d)

    if img_name not in file_refs:
        fid = f"{img_name} {clip_idx + 1}"
        file_refs[img_name] = fid
        fe = _add(clip, 'file', attrib={'id': fid})
        _add(fe, 'duration', 1440001)
        _rate(fe)
        _add(fe, 'name', img_name)
        _add(fe, 'pathurl', _url_path(seg['img_path']))
        tc = _add(fe, 'timecode')
        _add(tc, 'string', '00:00:00:00')
        _add(tc, 'displayformat', 'NDF')
        _rate(tc)
        media = _add(fe, 'media')
        vid = _add(media, 'video')
        _add(vid, 'duration', 1)
        sc = _add(vid, 'samplecharacteristics')
        _add(sc, 'width', 1920)
        _add(sc, 'height', 1080)
        file_defs.append(fe)
    else:
        _add(clip, 'file', attrib={'id': file_refs[img_name]})

    _add(clip, 'compositemode', 'normal')
    _filter_motion(clip, d)
    _filter_crop(clip, d)
    _filter_opacity(clip, d)
    _filter_timeremap(clip, d)
    _add(clip, 'comments')
    return clip


def _build_audio_clipitem(cl, clip_idx, file_defs, file_refs):
    d = cl['duration']
    wav_name = cl['wav_name']
    clip = _el('clipitem', attrib={'id': f"{wav_name} {clip_idx}"})
    _add(clip, 'name', wav_name)
    _add(clip, 'duration', d)
    _rate(clip)
    _add(clip, 'start', cl['start'])
    _add(clip, 'end', cl['end'])
    _add(clip, 'enabled', 'TRUE')
    _add(clip, 'in', 0)
    _add(clip, 'out', d)

    if wav_name not in file_refs:
        fid = f"{wav_name} {clip_idx + 1}"
        file_refs[wav_name] = fid
        fe = _add(clip, 'file', attrib={'id': fid})
        _add(fe, 'duration', d)
        _rate(fe)
        _add(fe, 'name', wav_name)
        _add(fe, 'pathurl', _url_path(cl['wav_path']))
        media = _add(fe, 'media')
        aud = _add(media, 'audio')
        _add(aud, 'channelcount', 2)
        file_defs.append(fe)
    else:
        _add(clip, 'file', attrib={'id': file_refs[wav_name]})

    st = _add(clip, 'sourcetrack')
    _add(st, 'mediatype', 'audio')
    _add(st, 'trackindex', 1)
    _filter_audio_levels(clip, d)
    _filter_audio_pan(clip, d)
    _add(clip, 'comments')
    return clip


# ── 主生成 ──────────────────────────────────────────────────


def generate_xml(title, clips):
    if not clips:
        return None

    total_duration = clips[-1]['end']
    segments = _group_video_segments(clips)

    root = _el('xmeml', attrib={'version': '5'})
    seq = _add(root, 'sequence')
    _add(seq, 'name', title)
    _add(seq, 'duration', total_duration)
    _rate(seq)
    _add(seq, 'in', -1)
    _add(seq, 'out', -1)
    tc = _add(seq, 'timecode')
    _add(tc, 'string', '01:00:00:00')
    _add(tc, 'frame', TC_OFFSET)
    _add(tc, 'displayformat', 'NDF')
    _rate(tc)

    media = _add(seq, 'media')

    # ── 视频轨道 ──
    video = _add(media, 'video')
    vtrack = _add(video, 'track')
    file_defs = []
    file_refs = {}
    for i, seg in enumerate(segments):
        vtrack.append(_build_video_clipitem(seg, i, file_defs, file_refs))
    _add(vtrack, 'enabled', 'TRUE')
    _add(vtrack, 'locked', 'FALSE')

    fmt = _add(video, 'format')
    sc = _add(fmt, 'samplecharacteristics')
    _add(sc, 'width', 1920)
    _add(sc, 'height', 1080)
    _add(sc, 'pixelaspectratio', 'square')
    _rate(sc)
    codec = _add(sc, 'codec')
    appdata = _add(codec, 'appspecificdata')
    _add(appdata, 'appname', 'Final Cut Pro')
    _add(appdata, 'appmanufacturer', 'Apple Inc.')
    data = _add(appdata, 'data')
    _add(data, 'qtcodec')

    # ── 音频轨道 ──
    audio = _add(media, 'audio')
    atrack = _add(audio, 'track')
    for i, cl in enumerate(clips):
        atrack.append(_build_audio_clipitem(cl, i, file_defs, file_refs))
    _add(atrack, 'enabled', 'TRUE')
    _add(atrack, 'locked', 'FALSE')

    # ── 输出 ──
    rough = ET.tostring(root, encoding='unicode', xml_declaration=False)
    dom = minidom.parseString(rough)
    lines = dom.toprettyxml(indent='    ', encoding='UTF-8').decode('utf-8')
    return lines


def process_yaml(yaml_path):
    print(f"处理: {yaml_path}")
    title, clips = collect_clips(yaml_path)
    if not clips:
        print("  [警告] 没有有效的片段，跳过")
        return None

    xml = generate_xml(title, clips)
    if not xml:
        return None

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    basename = os.path.splitext(os.path.basename(yaml_path))[0]
    output_path = os.path.join(OUTPUT_DIR, f"{basename}.xml")

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(xml)

    print(f"  生成: {output_path}")
    print(f"  标题: {title}")
    print(f"  片段: {len(clips)} 个")
    print(f"  总时长: {clips[-1]['end']} 帧 ({clips[-1]['end'] / TIMEBASE:.1f} 秒)")
    return output_path


if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print("用法:")
        print("  单文件: python -m src.timeline_generator scripts/sample.yaml")
        print("  批量:   python -m src.timeline_generator --all")
        sys.exit(1)

    if sys.argv[1] == '--all':
        yaml_files = sorted(glob.glob(os.path.join('scripts', '*.yaml')))
        if not yaml_files:
            print("未找到 scripts/*.yaml 文件")
            sys.exit(1)
        print(f"找到 {len(yaml_files)} 个 YAML 文件\n")
        for yf in yaml_files:
            process_yaml(yf)
            print()
    else:
        yaml_path = sys.argv[1]
        if not os.path.exists(yaml_path):
            print(f"文件不存在: {yaml_path}")
            sys.exit(1)
        process_yaml(yaml_path)
