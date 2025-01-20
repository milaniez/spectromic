import multiprocessing as mp
import os
import pathlib
import queue as threading_queue
import re
import tkinter as tk
from datetime import datetime, timedelta
from tkinter import ttk

import matplotlib.pyplot as plt
import numpy as np
import scipy.io.wavfile as sp_wavfile
import sounddevice as sd


# Function to list all available input devices
# Ignoring devices with "Background Music" in their name
def list_audio_devices():
    devices = sd.query_devices()
    input_devices = [
        d
        for d in devices
        if d["max_input_channels"] > 0 and "Background Music" not in d["name"]
    ]
    for i, device in enumerate(input_devices):
        device["index"] = devices.index(device)
    return input_devices


# Function to display a single dialog to select device,
# sample rate, block size, file name, max amplitude value,
# amplitude scaling, frequency range, and WAV scaling parameter
def get_audio_settings(devices):
    def on_submit():
        selected_device.set(device_menu.get())
        selected_sample_rate.set(sample_rate_entry.get())
        selected_block_size.set(block_size_entry.get())
        selected_experiment_name.set(experiment_name_entry.get())
        selected_drone_name.set(drone_name_entry.get())
        selected_max_amplitude.set(max_amplitude_entry.get())
        selected_min_frequency.set(min_frequency_entry.get())
        selected_max_frequency.set(max_frequency_entry.get())
        selected_length.set(length_entry.get())
        root.destroy()

    root = tk.Tk()
    root.title("Audio Settings")

    # Dropdown for audio device selection
    tk.Label(root, text="Select Audio Device:").grid(row=0, column=0)
    device_names = [f"{d['index']}: {d['name']}" for d in devices]
    selected_device = tk.StringVar(value=device_names[0])
    device_menu = ttk.Combobox(root, textvariable=selected_device, values=device_names)
    device_menu.grid(row=0, column=1)

    # Entry for sample rate
    tk.Label(root, text="Sample Rate:").grid(row=1, column=0)
    selected_sample_rate = tk.StringVar(value="48000")
    sample_rate_entry = tk.Entry(root, textvariable=selected_sample_rate)
    sample_rate_entry.grid(row=1, column=1)

    # Entry for block size
    tk.Label(root, text="Block Size:").grid(row=2, column=0)
    selected_block_size = tk.StringVar(value="1200")
    block_size_entry = tk.Entry(root, textvariable=selected_block_size)
    block_size_entry.grid(row=2, column=1)

    # Entry for experiment name
    tk.Label(root, text="Experiment Name:").grid(row=3, column=0)
    selected_experiment_name = tk.StringVar(value="experiment")
    experiment_name_entry = tk.Entry(root, textvariable=selected_experiment_name)
    experiment_name_entry.grid(row=3, column=1)

    # Entry for drone name
    tk.Label(root, text="Drone Name:").grid(row=4, column=0)
    selected_drone_name = tk.StringVar(value="drone")
    drone_name_entry = tk.Entry(root, textvariable=selected_drone_name)
    drone_name_entry.grid(row=4, column=1)

    # Entry for max amplitude value
    tk.Label(root, text="Max Amplitude:").grid(row=5, column=0)
    selected_max_amplitude = tk.StringVar(value="10")
    max_amplitude_entry = tk.Entry(root, textvariable=selected_max_amplitude)
    max_amplitude_entry.grid(row=5, column=1)

    # Entry for minimum frequency
    tk.Label(root, text="Min Frequency (Hz):").grid(row=6, column=0)
    selected_min_frequency = tk.StringVar(value="0")
    min_frequency_entry = tk.Entry(root, textvariable=selected_min_frequency)
    min_frequency_entry.grid(row=6, column=1)

    # Entry for maximum frequency
    tk.Label(root, text="Max Frequency (Hz):").grid(row=7, column=0)
    selected_max_frequency = tk.StringVar(value="24000")
    max_frequency_entry = tk.Entry(root, textvariable=selected_max_frequency)
    max_frequency_entry.grid(row=7, column=1)

    # Option for amplitude scaling
    tk.Label(root, text="Amplitude Scaling:").grid(row=8, column=0)
    amplitude_scaling_var = tk.StringVar(value="Linear")
    amplitude_scaling_menu = ttk.Combobox(
        root, textvariable=amplitude_scaling_var, values=["Logarithmic", "Linear"]
    )
    amplitude_scaling_menu.grid(row=8, column=1)

    # Entry for length
    tk.Label(root, text="Length (seconds):").grid(row=9, column=0)
    selected_length = tk.StringVar(value="60")
    length_entry = tk.Entry(root, textvariable=selected_length)
    length_entry.grid(row=9, column=1)

    # Submit button
    submit_button = tk.Button(root, text="Submit", command=on_submit)
    submit_button.grid(row=10, columnspan=2)

    root.mainloop()

    return (
        int(selected_device.get().split(":")[0]),
        int(selected_sample_rate.get()),
        int(selected_block_size.get()),
        selected_experiment_name.get(),
        selected_drone_name.get(),
        float(selected_max_amplitude.get()),
        float(selected_min_frequency.get()),
        float(selected_max_frequency.get()),
        amplitude_scaling_var.get(),
        int(selected_length.get()),
    )


# Function to capture audio in a separate process and save to a .wav file
def audio_capture_process(out_queue, device_id, sample_rate, blocksize):
    print(
        f"Device ID: {device_id}, Sample Rate: {sample_rate}, Block Size: {blocksize}, "
    )
    internal_queue = threading_queue.Queue()
    adc_time_offset = None

    def audio_callback(indata, frames, time, status):
        current_time = datetime.now().timestamp()
        nonlocal adc_time_offset
        if status:
            print(status)

        adc_time = time.inputBufferAdcTime
        if adc_time_offset is None:
            adc_time_offset = current_time - adc_time

        adjusted_adc_time = adc_time + adc_time_offset
        # print(
        #     f"ADC Time: {adjusted_adc_time}, "
        #     f"Current Time: {current_time}, "
        #     f"Offset: {adc_time_offset}, "
        #     f"Input Buffer Time: {time.inputBufferAdcTime}, "
        #     f"Current Time: {time.currentTime}"
        # )
        internal_queue.put((indata.copy(), adjusted_adc_time))

    def send_data():
        while True:
            try:
                data, adjusted_time = internal_queue.get()
                out_queue.put((data, adjusted_time))
            except Exception as e:
                print(f"Error in sending data: {e}")
                break

    with sd.InputStream(
        device=device_id,
        channels=1,
        samplerate=sample_rate,
        blocksize=blocksize,
        callback=audio_callback,
        clip_off=True,
        dither_off=True,
    ):
        send_data()


# Function to start the live spectrogram
def start_spectrogram(
    queue,
    sample_rate,
    block_size,
    max_amplitude,
    min_freq,
    max_freq,
    scaling,
    experiment_folder_path,
    length,
):
    plt.ion()
    fig, ax = plt.subplots()
    time_window = 10  # Display the last 10 seconds
    freq_bins = np.fft.rfftfreq(block_size, 1 / sample_rate)
    min_bin = np.searchsorted(freq_bins, min_freq)
    max_bin = np.searchsorted(freq_bins, max_freq)

    wave_file_path = os.path.join(experiment_folder_path, "output.wav")
    all_data = np.zeros(sample_rate * length, dtype=np.float32)
    print(f"shape of all_data: {np.shape(all_data)}")
    all_data_len = 0

    Z = np.zeros((max_bin - min_bin, time_window * sample_rate // block_size))

    min_value = -10 if scaling == "Logarithmic" else 0
    img = ax.imshow(
        Z,
        aspect="auto",
        origin="lower",
        extent=[0, time_window, min_freq, max_freq],
        cmap="magma",
        vmin=min_value,
        vmax=max_amplitude,
    )
    plt.colorbar(img)
    ax.set_xlabel("Time")
    ax.set_ylabel("Frequency (Hz)")

    start_time = None
    last_plot_save_time = None
    last_plot_save_no = 0
    last_time = None
    try:
        while plt.fignum_exists(fig.number) and all_data_len < len(all_data):
            while not queue.empty() and all_data_len < len(all_data):
                data, adjusted_time = queue.get()
                print(f"shape of data: {np.shape(data)}")
                all_data[all_data_len : all_data_len + len(data)] = data.flatten()
                all_data_len += len(data)
                print(np.shape(data))
                spectrum = np.abs(np.fft.rfft(data[:, 0]))[min_bin:max_bin]
                if scaling == "Logarithmic":
                    spectrum = 10 * np.log10(
                        spectrum + 1e-12
                    )  # Convert amplitude to dB scale
                elif np.max(spectrum) > max_amplitude:
                    print("\033[91m\033[1mMax amplitude exceeded\033[0m")
                    print(
                        f"max data {np.max(data)} "
                        f"min data {np.min(data)} "
                        f"max spectrum {np.max(spectrum)} "
                        f"min spectrum {np.min(spectrum)}"
                    )

                # print(
                #     f"max data {np.max(data)} "
                #     f"min data {np.min(data)} "
                #     f"max spectrum {np.max(spectrum)} "
                #     f"min spectrum {np.min(spectrum)}"
                # )

                Z[:, :-1] = Z[:, 1:]
                Z[:, -1] = spectrum

                if start_time is None:
                    start_time = adjusted_time
                    last_plot_save_time = adjusted_time
                last_time = adjusted_time

                # Update the x-axis to show real local time
                current_time = datetime.fromtimestamp(adjusted_time)
                time_labels = [
                    (current_time - timedelta(seconds=time_window - i)).strftime(
                        "%H:%M:%S"
                    )
                    for i in range(time_window)
                ]
                ax.set_xticks(np.linspace(0, time_window, len(time_labels)))
                ax.set_xticklabels(time_labels, rotation=45)

                img.set_data(Z)

                if last_time - last_plot_save_time >= 1.0:
                    plot_file_path = os.path.join(
                        experiment_folder_path,
                        f"plot_{last_plot_save_no}.png",
                    )
                    plt.savefig(plot_file_path)
                    last_plot_save_no += 1
                    last_plot_save_time = last_time
            plt.pause(0.01)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Error: {e}")
    finally:
        print("\033[93m\033[1mSaving...\033[0m")
        sp_wavfile.write(wave_file_path, sample_rate, all_data[0:all_data_len])
        total_seconds_displayed = (
            last_time - start_time + block_size / sample_rate if start_time else 0
        )
        print(
            f"Total number of seconds displayed: {total_seconds_displayed:.2f} seconds"
        )
        plt.close()


def is_valid_filename(filename):
    # Define the set of invalid characters for Windows and Linux
    invalid_characters = (
        r'[<>:"/\\|?*\x00-\x1F]'  # Includes control characters (\x00-\x1F)
    )
    reserved_names = {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        "COM1",
        "COM2",
        "COM3",
        "COM4",
        "COM5",
        "COM6",
        "COM7",
        "COM8",
        "COM9",
        "LPT1",
        "LPT2",
        "LPT3",
        "LPT4",
        "LPT5",
        "LPT6",
        "LPT7",
        "LPT8",
        "LPT9",
    }

    # Check for invalid characters
    if re.search(invalid_characters, filename):
        return False

    # Check for reserved names (case-insensitive)
    if filename.upper() in reserved_names:
        return False

    # Check if the filename is "." or ".."
    if filename in {".", ".."}:
        return False

    return True


if __name__ == "__main__":
    devices = list_audio_devices()
    if not devices:
        print("No input devices found.")
        exit(1)

    (
        selected_device_id,
        selected_sample_rate,
        blocksize,
        experiment_name,
        drone_name,
        max_amplitude,
        min_frequency,
        max_frequency,
        scaling,
        length,
    ) = get_audio_settings(devices)

    if not is_valid_filename(experiment_name):
        print("Invalid experiment name. Please choose a different name.")
        exit(1)

    if not is_valid_filename(drone_name):
        print("Invalid drone name. Please choose a different name.")
        exit(1)

    if selected_sample_rate % blocksize != 0:
        print("Sample rate must be a multiple of block size.")
        exit(1)

    experiment_folder_name = f"{datetime.now().strftime('%Y%m%d-%H%M%S')}_"
    experiment_folder_name += f"{experiment_name.replace(' ', '-')}_"
    experiment_folder_name += f"{drone_name.replace(' ', '-')}"

    experiment_folder_path = os.path.join(
        os.getcwd(),
        "experiments",
        experiment_folder_name,
    )

    pathlib.Path(experiment_folder_path).mkdir(parents=True, exist_ok=True)

    selected_device = devices[
        [i for i in range(len(devices)) if devices[i]["index"] == selected_device_id][0]
    ]

    print(f"Selected Device: {selected_device['name']} at index {selected_device_id}")
    print(f"Selected Sample Rate: {selected_sample_rate}")
    print(f"Selected Block Size: {blocksize}")
    print(f"Experiment Folder: {experiment_folder_name}")
    print(f"Max Amplitude for Spectrogram: {max_amplitude}")
    print(f"Min Frequency: {min_frequency} Hz, Max Frequency: {max_frequency} Hz")
    print(f"Amplitude Scaling: {scaling}")
    print(f"Experiment Length: {length} seconds")

    audio_queue = mp.Queue()
    audio_process = mp.Process(
        target=audio_capture_process,
        args=(
            audio_queue,
            selected_device_id,
            selected_sample_rate,
            blocksize,
        ),
    )
    audio_process.daemon = True
    audio_process.start()

    start_spectrogram(
        audio_queue,
        selected_sample_rate,
        blocksize,
        max_amplitude,
        min_frequency,
        max_frequency,
        scaling,
        experiment_folder_path,
        length,
    )
