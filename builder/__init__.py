import sys
import os
import subprocess


def update_mphalport(target):
    if target == 'esp8266':
        mphalport_path = f'lib/micropython/ports/{target}/esp_mphal.h'
    elif target == 'pic16bit':
        mphalport_path = f'lib/micropython/ports/{target}/pic16bit_mphal.h'
    elif target == 'teensy':
        mphalport_path = f'lib/micropython/ports/{target}/teensy_hal.h'
    else:
        mphalport_path = f'lib/micropython/ports/{target}/mphalport.h'

    if not os.path.exists(mphalport_path):
        raise RuntimeError(mphalport_path)

    with open(mphalport_path, 'rb') as f:
        data = f.read().decode('utf-8')

    if '#ifndef _MPHALPORT_H_' not in data:
        data = f'#ifndef _MPHALPORT_H_\n#define _MPHALPORT_H_\n{data}\n#endif /* _MPHALPORT_H_ */\n'
        with open(mphalport_path, 'wb') as f:
            f.write(data.encode('utf-8'))


def generate_manifest(manifest_path, frozen_manifest, *addl_manifest_files):
    if not os.path.exists('build'):
        os.mkdir('build')

    manifest_files = [
        f"include('{os.path.abspath(manifest_path)}')"
    ]

    if frozen_manifest is not None:
        manifest_files.append(f"include('{frozen_manifest}')")

    for file in addl_manifest_files:
        print(file)
        if not os.path.exists(file):
            raise RuntimeError(f'File not found "{file}"')

        file_path, file_name = os.path.split(file)
        entry = f"freeze('{file_path}', '{file_name}')"
        manifest_files.append(entry)

    manifest_files = '\n'.join(manifest_files)

    with open('build/manifest.py', 'w') as f:
        f.write(manifest_files)


def get_lvgl():
    cmd_ = [
        'git',
        'submodule',
        'init',
        '--update',
        '--',
        f'lib/lvgl'
    ]
    result, _ = spawn(cmd_)
    if result != 0:
        sys.exit(result)


def get_micropython():
    cmd_ = [
        'git',
        'submodule',
        'update',
        '--init',
        '--',
        f'lib/micropython'
    ]

    result, _ = spawn(cmd_)
    if result != 0:
        sys.exit(result)


def get_pycparser():
    cmd_ = [
        'git',
        'submodule',
        'update',
        '--init',
        '--',
        f'lib/pycparser'
    ]

    result, _ = spawn(cmd_)
    if result != 0:
        sys.exit(result)


def spawn(cmd_, out_to_screen=True):

    if sys.platform.startswith('win'):
        prompt = b'>'
    else:
        prompt = b'$'

    if isinstance(cmd_[0], str):
        cmd_ = ' '.join(cmd_) + '\n'
    else:
        cmd_ = ' && '.join(' '.join(c) + '\n' for c in cmd_)

    def read():
        output_buffer = b''
        while p.poll() is None:
            o_char = p.stdout.read(1)
            while o_char != b'':
                if out_to_screen:
                    sys.stdout.write(o_char.decode('utf-8'))
                    sys.stdout.flush()
                output_buffer += o_char
                o_char = p.stdout.read(1)

            e_char = p.stderr.read(1)
            while e_char != b'':
                if out_to_screen:
                    try:
                        sys.stderr.write(e_char.decode('utf-8'))
                    except UnicodeDecodeError:
                        sys.stderr.write(repr(e_char))
                    sys.stderr.flush()
                output_buffer += e_char
                e_char = p.stderr.read(1)

            if output_buffer.endswith(prompt):
                break

        return output_buffer

    p = subprocess.Popen(
        cmd_,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=True
    )

    # print(cmd_[:-1])
    o_buf = read().decode('utf-8')

    if not p.stdout.closed:
        p.stdout.close()

    if not p.stderr.closed:
        p.stderr.close()

    return p.returncode, o_buf


def clean():
    spawn(clean_cmd)


def submodules():
    return_code, _ = spawn(submodules_cmd)
    if return_code != 0:
        sys.exit(return_code)


def compile():  # NOQA
    return_code, _ = spawn(compile_cmd)
    if return_code != 0:
        sys.exit(return_code)


def mpy_cross():
    return_code, _ = spawn(mpy_cross_cmd)
    if return_code != 0:
        sys.exit(return_code)


def build_manifest(target, script_dir, frozen_manifest):
    update_mphalport(target)
    if target == 'teensy':
        manifest_path = f'lib/micropython/ports/{target}/manifest.py'
    else:
        manifest_path = f'lib/micropython/ports/{target}/boards/manifest.py'

    if not os.path.exists(manifest_path):
        raise RuntimeError(f'Unable to locate manifest file "{manifest_path}"')

    manifest_files = [
        f'{script_dir}/driver/display/display_driver_framework.py',
        f'{script_dir}/driver/fs_driver.py',
        f'{script_dir}/utils/lv_utils.py',
    ]

    generate_manifest(manifest_path, frozen_manifest, *manifest_files)


def parse_args(extra_args, lv_cflags, board):
    return extra_args, lv_cflags, board


mpy_cross_cmd = ['make', '-C', 'lib/micropython/mpy-cross']
cmd = [
    'make',
    '',
    f'-j {os.cpu_count()}',
    '-C'
]
clean_cmd = []
compile_cmd = []
submodules_cmd = []


def build_commands(target, extra_args, script_dir, lv_cflags, board):
    if target == 'samd':
        if lv_cflags is None:
            lv_cflags = '-DLV_USE_TINY_TTF=0'
        else:
            lv_cflags += ' -DLV_USE_TINY_TTF=0'

    cmd.extend([
        f'lib/micropython/ports/{target}',
        f'LV_PORT={target}',
    ])

    if lv_cflags is not None:
        cmd.append(f'LV_CFLAGS="{lv_cflags}"')

    if board is not None:
        if lv_cflags is not None:
            cmd.insert(5, f'BOARD={board}')
        else:
            cmd.append(f'BOARD={board}')

    cmd.append(f'USER_C_MODULES={script_dir}/ext_mod')
    cmd.extend(extra_args)

    clean_cmd.extend(cmd[:])
    clean_cmd[1] = 'clean'

    compile_cmd.extend(cmd[:])
    compile_cmd.pop(1)

    submodules_cmd.extend(cmd[:])
    submodules_cmd[1] = 'submodules'