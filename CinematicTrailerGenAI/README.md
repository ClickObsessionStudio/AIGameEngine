# Generate a new video from text (Text-to-video)
python run_cinematic_trailer_gen.py --prompt "a boy and a girl run into a classical ramen shop. they enjoy eating ramen a lot. very fast paced scenes with high level camera zooming down and switching into close-up enjoyable eating inside the ramen shop. animated style ultra high quality. 8k." -- --resize_mode all --output_filename "ramen2.mp4"

# Edit a landscape video to portrait video:
cinematic_env/Scripts/python.exe run_cinematic_trailer_gen.py --input "generated_media/ramen2.mp4" --resize_mode all

