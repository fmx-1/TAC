
import sys
import os
import numpy as np
import torch
import torchvision
from torch import nn
import torch.nn.functional as F
from transformers import CLIPModel
from torchvision import datasets, transforms
import torchvision.transforms as transforms
import clip 
import random
from torch.utils.data import DataLoader, Subset

def set_model_clip(args):
    '''
    load Huggingface CLIP
    '''
    ckpt_mapping = {"ViT-B/16":"/media/chaod/code/MCM/checkpoint/clip-vit-base-patch16", 
                    "ViT-B/32":"/media/chaod/code/MCM/checkpoint/clip-vit-base-patch32",
                    "ViT-L/14":"/media/chaod/code/MCM/checkpoint/clip-vit-large-patch14"}
    args.ckpt = ckpt_mapping[args.CLIP_ckpt]
    # device = "cuda" if torch.cuda.is_available() else "cpu"
    # model, transform = clip.load("ViT-B/32", device=device)
    model =  CLIPModel.from_pretrained(args.ckpt)
    if args.model == 'CLIP-Linear':
        model.load_state_dict(torch.load(args.finetune_ckpt, map_location=torch.device(args.gpu)))
    model = model.cuda()
    normalize = transforms.Normalize(mean=(0.48145466, 0.4578275, 0.40821073),
                                         std=(0.26862954, 0.26130258, 0.27577711))  # for CLIP
    val_preprocess = transforms.Compose([
            transforms.Resize(224),
            transforms.CenterCrop(224),
            transforms.ToTensor(),
            normalize
        ])
    
    return model, val_preprocess

def set_train_loader(args, preprocess=None, batch_size=None, shuffle=False, subset=False):
    root = args.root_dir
    if preprocess == None:
        normalize = transforms.Normalize(mean=(0.48145466, 0.4578275, 0.40821073),
                                         std=(0.26862954, 0.26130258, 0.27577711))  # for CLIP
        preprocess = transforms.Compose([
            transforms.RandomCrop(32, padding=4),
            transforms.RandomHorizontalFlip(),
            transforms.ToTensor(),
            normalize
        ])
    kwargs = {'num_workers': 4, 'pin_memory': True}
    if batch_size is None:  # normal case: used for trainign
        batch_size = args.batch_size
        shuffle = True
    if args.in_dataset == "ImageNet":
        path = os.path.join(root, 'ImageNet', 'train')
        dataset = datasets.ImageFolder(path, transform=preprocess)
        if subset:
            from collections import defaultdict
            classwise_count = defaultdict(int)
            indices = []
            for i, label in enumerate(dataset.targets):
                if classwise_count[label] < args.max_count:
                    indices.append(i)
                    classwise_count[label] += 1
            dataset = torch.utils.data.Subset(dataset, indices)
        train_loader = torch.utils.data.DataLoader(dataset,
                                                   batch_size=batch_size, shuffle=shuffle, **kwargs)
    elif args.in_dataset in ["ImageNet10", "ImageNet20", "ImageNet100"]:
        train_loader = torch.utils.data.DataLoader(
            datasets.ImageFolder(os.path.join(
                root, args.in_dataset, 'train'), transform=preprocess),
            batch_size=batch_size, shuffle=shuffle, **kwargs)
    elif args.in_dataset == "car196":
        train_loader = torch.utils.data.DataLoader(StanfordCars(root, split="train", download=True, transform=preprocess),
                                                   batch_size=batch_size, shuffle=shuffle, **kwargs)
    elif args.in_dataset == "food101":
        train_loader = torch.utils.data.DataLoader(Food101(root, split="train", download=True, transform=preprocess),
                                                   batch_size=batch_size, shuffle=shuffle, **kwargs)
    elif args.in_dataset == "pet37":
        train_loader = torch.utils.data.DataLoader(OxfordIIITPet(root, split="trainval", download=True, transform=preprocess),
                                                   batch_size=batch_size, shuffle=shuffle, **kwargs)
    elif args.in_dataset == "bird200":
        train_loader = torch.utils.data.DataLoader(Cub2011(root, train = True, transform=preprocess),
                    batch_size=batch_size, shuffle=shuffle, **kwargs)
    elif args.in_dataset == "waterbird":
        def get_random_subset_indices(dataset, fraction):
            total_samples = len(dataset)
            subset_size = int(total_samples * fraction)
            return random.sample(range(total_samples), subset_size)
        full_dataset = datasets.ImageFolder(os.path.join(root, args.in_dataset), transform=preprocess)
        subset_indices = get_random_subset_indices(full_dataset, 0.1)
        subset_dataset = Subset(full_dataset, subset_indices)
        train_loader = DataLoader(
            subset_dataset, 
            batch_size=args.batch_size, 
            shuffle=False, 
            **kwargs
        )
    return train_loader


def set_val_loader(args, preprocess=None):
    root = args.root_dir
    if preprocess == None:
        normalize = transforms.Normalize(mean=(0.48145466, 0.4578275, 0.40821073),
                                         std=(0.26862954, 0.26130258, 0.27577711))  # for CLIP
        preprocess = transforms.Compose([
            transforms.ToTensor(),
            normalize
        ])
    kwargs = {'num_workers': 4, 'pin_memory': True}
    if args.in_dataset == "ImageNet":
        path = os.path.join(root, 'ImageNet', 'val')
        val_loader = torch.utils.data.DataLoader(
            datasets.ImageFolder(path, transform=preprocess),
            batch_size=args.batch_size, shuffle=False, **kwargs)
    elif args.in_dataset in ["ImageNet10", "ImageNet20", "ImageNet100"]:
        val_loader = torch.utils.data.DataLoader(
            datasets.ImageFolder(os.path.join(
                root, args.in_dataset, 'val'), transform=preprocess),
            batch_size=args.batch_size, shuffle=False, **kwargs)
    elif args.in_dataset == "car196":
        val_loader = torch.utils.data.DataLoader(
            datasets.ImageFolder(os.path.join(
                root, args.in_dataset,'test'), transform=preprocess),
            batch_size=args.batch_size, shuffle=False, **kwargs)
    elif args.in_dataset == "food101":
        val_loader = torch.utils.data.DataLoader(Food101(root, split="test", download=False, transform=preprocess),
                                                 batch_size=args.batch_size, shuffle=False, **kwargs)
    elif args.in_dataset == "pet37":
        val_loader = torch.utils.data.DataLoader(OxfordIIITPet(root, split="test", download=False, transform=preprocess),
                                                 batch_size=args.batch_size, shuffle=False, **kwargs)
    elif args.in_dataset == "bird200":
        val_loader = torch.utils.data.DataLoader(Cub2011(root, train = False, transform=preprocess),
                    batch_size=args.batch_size, shuffle=False, **kwargs)
    elif args.in_dataset == "cifar10":
        val_dataset = torchvision.datasets.CIFAR10(root='./datasets', train=False, download=False, transform=preprocess)
        val_loader = torch.utils.data.DataLoader(val_dataset, batch_size=args.batch_size, shuffle=False)
    elif args.in_dataset == 'cifar100':
        val_dataset = torchvision.datasets.CIFAR100(root='./datasets', train=False, download=False, transform=preprocess)
        val_loader = torch.utils.data.DataLoader(val_dataset, batch_size=args.batch_size, shuffle=False)
    elif args.in_dataset == "waterbird":
        val_loader = torch.utils.data.DataLoader(
            datasets.ImageFolder(os.path.join(
                root, args.in_dataset), transform=preprocess),
            batch_size=args.batch_size, shuffle=False, **kwargs)

    return val_loader


def set_ood_loader_ImageNet(args, out_dataset, preprocess, root):
    '''
    set OOD loader for ImageNet scale datasets
    '''
    if out_dataset == 'iNaturalist':
        testsetout = torchvision.datasets.ImageFolder(root=os.path.join(root, 'iNaturalist'), transform=preprocess)
    elif out_dataset == 'SUN':
        testsetout = torchvision.datasets.ImageFolder(root=os.path.join(root, 'SUN'), transform=preprocess)
    elif out_dataset == 'places365': # filtered places
        testsetout = torchvision.datasets.ImageFolder(root= os.path.join(root, 'Places'),transform=preprocess)   
    elif out_dataset == 'dtd':
        testsetout = torchvision.datasets.ImageFolder(root=os.path.join(root, 'dtd', 'images'),
                                        transform=preprocess)
        # testsetout = torchvision.datasets.ImageFolder(root=os.path.join(root, 'Textures'),
        #                                 transform=preprocess)
    elif out_dataset == 'SSB':
        testsetout = datasets.ImageFolder(root=os.path.join(args.root, 'ImageNet_OOD_dataset/ssb_hard'),
                                          transform=preprocess)
    elif out_dataset == 'Ninco':
        testsetout = datasets.ImageFolder(root=os.path.join(args.root, 'ImageNet_OOD_dataset/ninco'),
                                          transform=preprocess)
    elif out_dataset == 'ImageNet10':
        testsetout = datasets.ImageFolder(os.path.join(args.root_dir, 'ImageNet10', 'val'), transform=preprocess)
    elif out_dataset == 'ImageNet20':
        testsetout = datasets.ImageFolder(os.path.join(args.root_dir, 'ImageNet20', 'val'), transform=preprocess)
    elif out_dataset == "cifar10":
        testsetout = torchvision.datasets.CIFAR10(root='./datasets', train=False, download=False, transform=preprocess)
    elif out_dataset == 'cifar100':
        testsetout = torchvision.datasets.CIFAR100(root='./datasets', train=False, download=False, transform=preprocess)
    elif out_dataset =='lsun':
        testsetout = torchvision.datasets.ImageFolder(root = os.path.join(root, 'LSUN'),transform=preprocess)
    elif out_dataset =='tinyimagenet':
        testsetout = torchvision.datasets.ImageFolder(root = os.path.join(root, 'Tiny-Imagenet'),transform=preprocess)
    elif out_dataset =='Places_bg':
        testsetout = torchvision.datasets.ImageFolder(root = os.path.join(root, 'Placesbg'),transform=preprocess)

    testloaderOut = torch.utils.data.DataLoader(testsetout, batch_size=args.batch_size,
                                            shuffle=False, num_workers=4)
    return testloaderOut

