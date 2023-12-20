cd /braindat/lab/liusl/flywire/PointNet/Pointnet_Pointnet2_pytorch-master/ || exit
pip install plyfile
python test_classification_biological.py --model pointnet2_binary_ssg --log_dir connection_lr0005_bs92_wimage_2048_Unet --num_gpus 1 --batch_size 64 --learning_rate 0.0005 --image_feature biological_feature/extract_biological_pc_Unet --num_point 2048